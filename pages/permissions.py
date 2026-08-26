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

from .models import AboutPage, OurStoryPage


EDITORIAL_EDITOR_GROUP = "Editorial Editors"
EDITORIAL_PUBLISHER_GROUP = "Editorial Publishers"
EDITORIAL_ADMIN_GROUP = "Editorial Administrators"
EDITORIAL_MEDIA_COLLECTION = "Editorial media"
EDITORIAL_REVIEW_TASK = "Editorial publisher approval"
EDITORIAL_WORKFLOW = "Editorial review"

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
EDITOR_PAGE_PERMISSIONS = {"change_page"}
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
class EditorialRole:
    name: str
    model_permissions: frozenset[tuple[str, str]]
    page_permissions: frozenset[str]
    image_permissions: frozenset[str]


EDITORIAL_ROLES = (
    EditorialRole(
        EDITORIAL_EDITOR_GROUP,
        frozenset(EDITOR_MODEL_PERMISSIONS),
        frozenset(EDITOR_PAGE_PERMISSIONS),
        frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    EditorialRole(
        EDITORIAL_PUBLISHER_GROUP,
        frozenset(EDITOR_MODEL_PERMISSIONS),
        frozenset(PUBLISHER_PAGE_PERMISSIONS),
        frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    EditorialRole(
        EDITORIAL_ADMIN_GROUP,
        frozenset(ADMIN_MODEL_PERMISSIONS),
        frozenset(ADMIN_PAGE_PERMISSIONS),
        frozenset(ADMIN_IMAGE_PERMISSIONS),
    ),
)


class EditorialPermissionConfigurationError(RuntimeError):
    pass


def _permission(app_label, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist as exc:
        raise EditorialPermissionConfigurationError(
            f"Required permission {app_label}.{codename} does not exist. "
            "Run migrations first."
        ) from exc


def _default_site():
    try:
        return Site.objects.select_related("root_page").get(is_default_site=True)
    except Site.DoesNotExist as exc:
        raise EditorialPermissionConfigurationError(
            "A default Wagtail Site is required before editorial pages can be configured."
        ) from exc
    except Site.MultipleObjectsReturned as exc:
        raise EditorialPermissionConfigurationError(
            "Exactly one default Wagtail Site is required."
        ) from exc


def _get_or_create_page(site, page_model, *, slug, defaults):
    pages = list(page_model.objects.all())
    if len(pages) > 1:
        raise EditorialPermissionConfigurationError(
            f"More than one {page_model._meta.verbose_name} exists."
        )
    if pages:
        page = pages[0]
        if not page.path.startswith(site.root_page.path):
            raise EditorialPermissionConfigurationError(
                f"The {page_model._meta.verbose_name} is outside the default Site tree."
            )
        if page.slug != slug:
            raise EditorialPermissionConfigurationError(
                f"The {page_model._meta.verbose_name} must retain the /{slug}/ slug."
            )
        return page, False

    conflict = site.root_page.get_children().filter(slug=slug).first()
    if conflict is not None:
        raise EditorialPermissionConfigurationError(
            f"The /{slug}/ Wagtail path is already used by {conflict.specific_class}."
        )
    parent = site.root_page.specific
    if not page_model.can_create_at(parent):
        raise EditorialPermissionConfigurationError(
            f"The default Site root does not allow a {page_model._meta.verbose_name}."
        )

    page = page_model(slug=slug, live=False, show_in_menus=False, **defaults)
    parent.add_child(instance=page)
    page.save_revision()
    return page, True


def _get_or_create_editorial_pages():
    site = _default_site()
    about, about_created = _get_or_create_page(
        site,
        AboutPage,
        slug="about",
        defaults={
            "title": "About Jai Sri Krishna Jewellery",
            "search_description": (
                "Learn about Jai Sri Krishna Jewellery and its owner-managed gold "
                "and silver jewellery purchase plans in Vellore."
            ),
            "introduction": (
                "We are a jewellery business based in Thorapadi, Vellore, offering "
                "owner-managed gold and silver plans that help customers work toward "
                "an eligible showroom jewellery or coin purchase over time."
            ),
            "business_story": (
                "<p>We combine personal showroom guidance with a dependable digital "
                "record so enrolled customers can follow their journey clearly.</p>"
            ),
        },
    )
    story, story_created = _get_or_create_page(
        site,
        OurStoryPage,
        slug="our-story",
        defaults={
            "title": "Two brothers, one shared vision",
            "search_description": (
                "Meet brothers Dilip Kumar and Rajesh Rathod H, the business and "
                "technology minds behind Jai Sri Krishna Jewellery."
            ),
            "introduction": (
                "Jai Sri Krishna Jewellery brings together a love for serving customers "
                "and a passion for building dependable software."
            ),
            "business_owner_bio": (
                "<p>Dilip brings the business vision, jewellery experience, and "
                "customer-first approach that guide Jai Sri Krishna Jewellery and its "
                "savings schemes.</p>"
            ),
            "developer_bio": (
                "<p>Rajesh designed and developed the digital savings scheme platform, "
                "translating the store's working needs into a clear and dependable "
                "experience for customers and the owner.</p>"
            ),
            "partnership_story": (
                "<p>As brothers, Dilip and Rajesh combine business understanding with "
                "thoughtful software development. Their shared aim is to make every "
                "savings-scheme interaction more transparent, convenient, and "
                "personal.</p>"
            ),
        },
    )
    return (about, story), (about_created, story_created)


def _get_or_create_media_collection():
    root = Collection.get_first_root_node()
    if root is None:
        root = Collection.add_root(name="Root")
    collection = root.get_children().filter(name=EDITORIAL_MEDIA_COLLECTION).first()
    if collection is None:
        return root.add_child(name=EDITORIAL_MEDIA_COLLECTION), True
    return collection, False


def _configure_group(role, pages, media_collection):
    group, created = Group.objects.get_or_create(name=role.name)
    group.permissions.set(
        [_permission(app, code) for app, code in role.model_permissions]
    )
    GroupPagePermission.objects.filter(group=group).delete()
    for page in pages:
        for codename in role.page_permissions:
            GroupPagePermission.objects.create(
                group=group,
                page=page,
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


def _configure_workflow(pages, publisher_group, administrator_group):
    tasks = list(GroupApprovalTask.objects.filter(name=EDITORIAL_REVIEW_TASK))
    if len(tasks) > 1:
        raise EditorialPermissionConfigurationError(
            "Multiple editorial publisher approval tasks exist."
        )
    task_created = not tasks
    task = tasks[0] if tasks else GroupApprovalTask.objects.create(
        name=EDITORIAL_REVIEW_TASK,
        active=True,
    )
    if not task.active:
        task.active = True
        task.save(update_fields=["active"])
    task.groups.set([publisher_group, administrator_group])

    workflows = list(Workflow.objects.filter(name=EDITORIAL_WORKFLOW))
    if len(workflows) > 1:
        raise EditorialPermissionConfigurationError(
            "Multiple editorial review workflows exist."
        )
    workflow_created = not workflows
    workflow = workflows[0] if workflows else Workflow.objects.create(
        name=EDITORIAL_WORKFLOW,
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
            raise EditorialPermissionConfigurationError(
                "The editorial workflow has active submissions and cannot be reconciled safely."
            )
        WorkflowTask.objects.filter(workflow=workflow).delete()
        WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)

    for page in pages:
        WorkflowPage.objects.update_or_create(
            page=page,
            defaults={"workflow": workflow},
        )
    return workflow, task, workflow_created, task_created


@transaction.atomic
def configure_editorial_pages():
    pages, created_pages = _get_or_create_editorial_pages()
    media_collection, collection_created = _get_or_create_media_collection()
    groups = {}
    created_groups = []
    for role in EDITORIAL_ROLES:
        group, created = _configure_group(role, pages, media_collection)
        groups[role.name] = group
        if created:
            created_groups.append(role.name)
    workflow, task, workflow_created, task_created = _configure_workflow(
        pages,
        groups[EDITORIAL_PUBLISHER_GROUP],
        groups[EDITORIAL_ADMIN_GROUP],
    )
    return {
        "pages": pages,
        "created_pages": created_pages,
        "media_collection": media_collection,
        "collection_created": collection_created,
        "groups": groups,
        "created_groups": created_groups,
        "workflow": workflow,
        "workflow_created": workflow_created,
        "task": task,
        "task_created": task_created,
    }


def editorial_permission_configuration_errors():
    errors = []
    try:
        site = _default_site()
    except EditorialPermissionConfigurationError as exc:
        return [str(exc)]

    page_specs = ((AboutPage, "about"), (OurStoryPage, "our-story"))
    pages = []
    for page_model, slug in page_specs:
        matches = list(page_model.objects.all())
        if len(matches) != 1:
            errors.append(f"Exactly one {page_model._meta.verbose_name} must exist.")
            continue
        page = matches[0]
        pages.append(page)
        if not page.path.startswith(site.root_page.path):
            errors.append(f"The {page_model._meta.verbose_name} is outside the default Site tree.")
        if page.slug != slug:
            errors.append(f"The {page_model._meta.verbose_name} does not retain /{slug}/.")

    root_collection = Collection.get_first_root_node()
    media_collection = None
    if root_collection is not None:
        media_collection = root_collection.get_children().filter(
            name=EDITORIAL_MEDIA_COLLECTION
        ).first()
    if media_collection is None:
        errors.append("The dedicated editorial media collection is missing.")

    groups = {}
    for role in EDITORIAL_ROLES:
        try:
            group = Group.objects.get(name=role.name)
        except Group.DoesNotExist:
            errors.append(f"Group {role.name!r} is missing.")
            continue
        groups[role.name] = group
        if group.user_set.filter(is_staff=False).exists():
            errors.append(f"Group {role.name!r} contains a non-staff user.")
        if set(group.permissions.values_list("content_type__app_label", "codename")) != set(
            role.model_permissions
        ):
            errors.append(f"Group {role.name!r} has incorrect model permissions.")

        expected_page_permissions = {
            (page.pk, codename) for page in pages for codename in role.page_permissions
        }
        actual_page_permissions = set(
            GroupPagePermission.objects.filter(group=group).values_list(
                "page_id", "permission__codename"
            )
        )
        if actual_page_permissions != expected_page_permissions:
            errors.append(f"Group {role.name!r} has incorrect page permissions.")

        if media_collection is not None:
            expected_media_permissions = {
                (media_collection.pk, codename)
                for codename in role.image_permissions
            }
            actual_media_permissions = set(
                GroupCollectionPermission.objects.filter(group=group).values_list(
                    "collection_id", "permission__codename"
                )
            )
            if actual_media_permissions != expected_media_permissions:
                errors.append(f"Group {role.name!r} has incorrect media permissions.")

    try:
        workflow = Workflow.objects.get(name=EDITORIAL_WORKFLOW, active=True)
        task = GroupApprovalTask.objects.get(name=EDITORIAL_REVIEW_TASK, active=True)
    except (Workflow.DoesNotExist, GroupApprovalTask.DoesNotExist):
        errors.append("The active editorial review workflow or task is missing.")
        return errors
    except (Workflow.MultipleObjectsReturned, GroupApprovalTask.MultipleObjectsReturned):
        errors.append("Multiple active editorial review workflows or tasks exist.")
        return errors

    expected_reviewers = {
        groups[name].pk
        for name in (EDITORIAL_PUBLISHER_GROUP, EDITORIAL_ADMIN_GROUP)
        if name in groups
    }
    if set(task.groups.values_list("pk", flat=True)) != expected_reviewers:
        errors.append("The editorial approval task has incorrect reviewer groups.")
    task_ids = list(
        WorkflowTask.objects.filter(workflow=workflow)
        .order_by("sort_order", "pk")
        .values_list("task_id", flat=True)
    )
    if task_ids != [task.pk]:
        errors.append("The editorial review workflow has incorrect tasks.")
    for page in pages:
        if not WorkflowPage.objects.filter(page=page, workflow=workflow).exists():
            errors.append(f"The editorial workflow is not assigned to {page.title!r}.")
    return errors
