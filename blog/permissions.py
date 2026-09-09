from dataclasses import dataclass

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from wagtail.models import (
    Collection,
    GroupApprovalTask,
    GroupCollectionPermission,
    GroupPagePermission,
    Site,
    Workflow,
    WorkflowPage,
    WorkflowTask,
)

from .models import BlogIndexPage


BLOG_EDITOR_GROUP = "Blog Editors"
BLOG_PUBLISHER_GROUP = "Blog Publishers"
BLOG_ADMIN_GROUP = "Blog Administrators"
BLOG_MEDIA_COLLECTION = "Blog media"
BLOG_REVIEW_TASK = "Blog publisher approval"
BLOG_WORKFLOW = "Blog review"

EDITOR_MODEL_PERMISSIONS = {
    ("wagtailadmin", "access_admin"),
    ("wagtailimages", "view_image"),
    ("wagtailimages", "choose_image"),
    ("wagtailimages", "add_image"),
    ("wagtailimages", "change_image"),
}
ADMIN_MODEL_PERMISSIONS = EDITOR_MODEL_PERMISSIONS | {
    ("wagtailimages", "delete_image"),
}
EDITOR_PAGE_PERMISSIONS = {"add_page", "change_page"}
PUBLISHER_PAGE_PERMISSIONS = EDITOR_PAGE_PERMISSIONS | {
    "publish_page",
    "lock_page",
    "unlock_page",
}
ADMIN_PAGE_PERMISSIONS = PUBLISHER_PAGE_PERMISSIONS | {"bulk_delete_page"}
EDITOR_IMAGE_PERMISSIONS = {
    "view_image",
    "choose_image",
    "add_image",
    "change_image",
}
ADMIN_IMAGE_PERMISSIONS = EDITOR_IMAGE_PERMISSIONS | {"delete_image"}


@dataclass(frozen=True)
class BlogRole:
    name: str
    model_permissions: frozenset[tuple[str, str]]
    page_permissions: frozenset[str]
    image_permissions: frozenset[str]


BLOG_ROLES = (
    BlogRole(
        BLOG_EDITOR_GROUP,
        frozenset(EDITOR_MODEL_PERMISSIONS),
        frozenset(EDITOR_PAGE_PERMISSIONS),
        frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    BlogRole(
        BLOG_PUBLISHER_GROUP,
        frozenset(EDITOR_MODEL_PERMISSIONS),
        frozenset(PUBLISHER_PAGE_PERMISSIONS),
        frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    BlogRole(
        BLOG_ADMIN_GROUP,
        frozenset(ADMIN_MODEL_PERMISSIONS),
        frozenset(ADMIN_PAGE_PERMISSIONS),
        frozenset(ADMIN_IMAGE_PERMISSIONS),
    ),
)


class BlogPermissionConfigurationError(RuntimeError):
    pass


def _permission(app_label, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist as exc:
        raise BlogPermissionConfigurationError(
            f"Required permission {app_label}.{codename} does not exist. "
            "Run migrations first."
        ) from exc


def _default_site():
    try:
        return Site.objects.select_related("root_page").get(is_default_site=True)
    except Site.DoesNotExist as exc:
        raise BlogPermissionConfigurationError(
            "A default Wagtail Site is required before the blog can be configured."
        ) from exc
    except Site.MultipleObjectsReturned as exc:
        raise BlogPermissionConfigurationError(
            "Exactly one default Wagtail Site is required."
        ) from exc


def _get_or_create_blog_root():
    site = _default_site()
    blogs = list(BlogIndexPage.objects.all())
    if len(blogs) > 1:
        raise BlogPermissionConfigurationError(
            "More than one blog index exists; resolve the page tree first."
        )
    if blogs:
        blog = blogs[0]
        if not blog.path.startswith(site.root_page.path):
            raise BlogPermissionConfigurationError(
                "The blog index must be inside the default Site tree."
            )
        if blog.slug != "blog":
            raise BlogPermissionConfigurationError(
                "The blog index must retain the /blog/ slug."
            )
        return blog, False

    parent = site.root_page.specific
    if not BlogIndexPage.can_create_at(parent):
        raise BlogPermissionConfigurationError(
            "The default Site root does not allow a blog index child."
        )
    if parent.get_children().filter(slug="blog").exists():
        raise BlogPermissionConfigurationError(
            "The /blog/ path is already used by another Wagtail page."
        )

    blog = BlogIndexPage(
        title="Jewellery journal",
        slug="blog",
        intro=(
            "Practical jewellery guidance, care notes, and stories from "
            "Jai Sri Krishna Jewellery in Vellore."
        ),
        live=False,
        show_in_menus=False,
    )
    parent.add_child(instance=blog)
    blog.save_revision()
    return blog, True


def _get_or_create_media_collection():
    root = Collection.get_first_root_node()
    if root is None:
        root = Collection.add_root(name="Root")
    collection = root.get_children().filter(name=BLOG_MEDIA_COLLECTION).first()
    if collection is None:
        return root.add_child(name=BLOG_MEDIA_COLLECTION), True
    return collection, False


def _configure_group(role, blog, media_collection):
    group, created = Group.objects.get_or_create(name=role.name)
    group.permissions.set(
        [_permission(app, code) for app, code in role.model_permissions]
    )
    GroupPagePermission.objects.filter(group=group).delete()
    for codename in role.page_permissions:
        GroupPagePermission.objects.create(
            group=group,
            page=blog,
            permission=_permission("wagtailcore", codename),
        )
    GroupCollectionPermission.objects.filter(group=group).delete()
    for codename in role.image_permissions:
        GroupCollectionPermission.objects.create(
            group=group,
            collection=media_collection,
            permission=_permission("wagtailimages", codename),
        )
    return group, created


def _configure_workflow(blog, publisher_group, administrator_group):
    tasks = list(GroupApprovalTask.objects.filter(name=BLOG_REVIEW_TASK))
    if len(tasks) > 1:
        raise BlogPermissionConfigurationError(
            "Multiple blog publisher approval tasks exist."
        )
    task_created = not tasks
    task = tasks[0] if tasks else GroupApprovalTask.objects.create(
        name=BLOG_REVIEW_TASK,
        active=True,
    )
    if not task.active:
        task.active = True
        task.save(update_fields=["active"])
    task.groups.set([publisher_group, administrator_group])

    workflows = list(Workflow.objects.filter(name=BLOG_WORKFLOW))
    if len(workflows) > 1:
        raise BlogPermissionConfigurationError("Multiple blog review workflows exist.")
    workflow_created = not workflows
    workflow = workflows[0] if workflows else Workflow.objects.create(
        name=BLOG_WORKFLOW,
        active=True,
    )
    if not workflow.active:
        workflow.active = True
        workflow.save(update_fields=["active"])

    current_task_ids = list(
        WorkflowTask.objects.filter(workflow=workflow)
        .order_by("sort_order", "pk")
        .values_list("task_id", flat=True)
    )
    if current_task_ids != [task.pk]:
        if workflow.workflow_states.filter(
            status__in=["in_progress", "needs_changes"]
        ).exists():
            raise BlogPermissionConfigurationError(
                "The blog workflow has active submissions and cannot be reconciled safely."
            )
        WorkflowTask.objects.filter(workflow=workflow).delete()
        WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)

    WorkflowPage.objects.update_or_create(
        page=blog,
        defaults={"workflow": workflow},
    )
    return workflow, task, workflow_created, task_created


@transaction.atomic
def configure_blog_permissions():
    blog, blog_created = _get_or_create_blog_root()
    media_collection, collection_created = _get_or_create_media_collection()
    groups = {}
    created_groups = []
    for role in BLOG_ROLES:
        group, created = _configure_group(role, blog, media_collection)
        groups[role.name] = group
        if created:
            created_groups.append(role.name)
    workflow, task, workflow_created, task_created = _configure_workflow(
        blog,
        groups[BLOG_PUBLISHER_GROUP],
        groups[BLOG_ADMIN_GROUP],
    )
    return {
        "blog": blog,
        "blog_created": blog_created,
        "media_collection": media_collection,
        "collection_created": collection_created,
        "groups": groups,
        "created_groups": created_groups,
        "workflow": workflow,
        "workflow_created": workflow_created,
        "task": task,
        "task_created": task_created,
    }


def blog_permission_configuration_errors():
    errors = []
    try:
        site = _default_site()
    except BlogPermissionConfigurationError as exc:
        return [str(exc)]

    blogs = list(BlogIndexPage.objects.all())
    if len(blogs) != 1:
        return ["Exactly one blog index must exist."]
    blog = blogs[0]
    if not blog.path.startswith(site.root_page.path):
        errors.append("The blog index is outside the default Site tree.")
    if blog.slug != "blog":
        errors.append("The blog index does not retain /blog/.")

    root_collection = Collection.get_first_root_node()
    media_collection = None
    if root_collection is not None:
        media_collection = root_collection.get_children().filter(
            name=BLOG_MEDIA_COLLECTION
        ).first()
    if media_collection is None:
        errors.append("The dedicated blog media collection is missing.")

    groups = {}
    for role in BLOG_ROLES:
        try:
            group = Group.objects.get(name=role.name)
        except Group.DoesNotExist:
            errors.append(f"Group {role.name!r} is missing.")
            continue
        groups[role.name] = group
        if group.user_set.filter(is_staff=False).exists():
            errors.append(f"Group {role.name!r} contains a non-staff user.")
        if set(
            group.permissions.values_list("content_type__app_label", "codename")
        ) != set(role.model_permissions):
            errors.append(f"Group {role.name!r} has incorrect model permissions.")

        expected_page_permissions = set(role.page_permissions)
        actual_page_permissions = set(
            GroupPagePermission.objects.filter(group=group, page=blog).values_list(
                "permission__codename", flat=True
            )
        )
        if (
            actual_page_permissions != expected_page_permissions
            or GroupPagePermission.objects.filter(group=group).count()
            != len(expected_page_permissions)
        ):
            errors.append(f"Group {role.name!r} has incorrect page permissions.")

        if media_collection is not None:
            actual_image_permissions = set(
                GroupCollectionPermission.objects.filter(
                    group=group,
                    collection=media_collection,
                ).values_list("permission__codename", flat=True)
            )
            if (
                actual_image_permissions != set(role.image_permissions)
                or GroupCollectionPermission.objects.filter(group=group).count()
                != len(role.image_permissions)
            ):
                errors.append(f"Group {role.name!r} has incorrect media permissions.")

    try:
        workflow = Workflow.objects.get(name=BLOG_WORKFLOW, active=True)
    except Workflow.DoesNotExist:
        errors.append("The active blog review workflow is missing.")
        return errors
    except Workflow.MultipleObjectsReturned:
        errors.append("Multiple active blog review workflows exist.")
        return errors

    try:
        task = GroupApprovalTask.objects.get(name=BLOG_REVIEW_TASK, active=True)
    except GroupApprovalTask.DoesNotExist:
        errors.append("The active blog publisher approval task is missing.")
        return errors
    except GroupApprovalTask.MultipleObjectsReturned:
        errors.append("Multiple active blog publisher approval tasks exist.")
        return errors

    expected_reviewer_ids = {
        groups[name].pk
        for name in (BLOG_PUBLISHER_GROUP, BLOG_ADMIN_GROUP)
        if name in groups
    }
    if set(task.groups.values_list("pk", flat=True)) != expected_reviewer_ids:
        errors.append("The blog approval task has incorrect reviewer groups.")
    if list(
        WorkflowTask.objects.filter(workflow=workflow)
        .order_by("sort_order", "pk")
        .values_list("task_id", flat=True)
    ) != [task.pk]:
        errors.append("The blog review workflow has incorrect tasks.")
    if not WorkflowPage.objects.filter(page=blog, workflow=workflow).exists():
        errors.append("The blog review workflow is not assigned to the blog root.")
    return errors
