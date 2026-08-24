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

from .models import CatalogIndexPage


CATALOG_EDITOR_GROUP = "Catalogue Editors"
CATALOG_PUBLISHER_GROUP = "Catalogue Publishers"
CATALOG_ADMIN_GROUP = "Catalogue Administrators"
CATALOG_MEDIA_COLLECTION = "Catalogue media"
CATALOG_REVIEW_TASK = "Catalogue publisher approval"
CATALOG_WORKFLOW = "Catalogue review"


EDITOR_MODEL_PERMISSIONS = {
    ("wagtailadmin", "access_admin"),
    ("catalog", "view_productcategory"),
    ("catalog", "add_productcategory"),
    ("catalog", "change_productcategory"),
    ("catalog", "view_productcollection"),
    ("catalog", "add_productcollection"),
    ("catalog", "change_productcollection"),
    ("wagtailimages", "view_image"),
    ("wagtailimages", "choose_image"),
    ("wagtailimages", "add_image"),
    ("wagtailimages", "change_image"),
}

ADMIN_MODEL_PERMISSIONS = EDITOR_MODEL_PERMISSIONS | {
    ("catalog", "delete_productcategory"),
    ("catalog", "delete_productcollection"),
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
class CatalogRole:
    name: str
    model_permissions: frozenset[tuple[str, str]]
    page_permissions: frozenset[str]
    image_permissions: frozenset[str]


CATALOG_ROLES = (
    CatalogRole(
        name=CATALOG_EDITOR_GROUP,
        model_permissions=frozenset(EDITOR_MODEL_PERMISSIONS),
        page_permissions=frozenset(EDITOR_PAGE_PERMISSIONS),
        image_permissions=frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    CatalogRole(
        name=CATALOG_PUBLISHER_GROUP,
        model_permissions=frozenset(EDITOR_MODEL_PERMISSIONS),
        page_permissions=frozenset(PUBLISHER_PAGE_PERMISSIONS),
        image_permissions=frozenset(EDITOR_IMAGE_PERMISSIONS),
    ),
    CatalogRole(
        name=CATALOG_ADMIN_GROUP,
        model_permissions=frozenset(ADMIN_MODEL_PERMISSIONS),
        page_permissions=frozenset(ADMIN_PAGE_PERMISSIONS),
        image_permissions=frozenset(ADMIN_IMAGE_PERMISSIONS),
    ),
)


class CatalogPermissionConfigurationError(RuntimeError):
    pass


def _permission(app_label, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist as exc:
        raise CatalogPermissionConfigurationError(
            f"Required permission {app_label}.{codename} does not exist. "
            "Run migrations first."
        ) from exc


def _get_default_site():
    try:
        return Site.objects.select_related("root_page").get(is_default_site=True)
    except Site.DoesNotExist as exc:
        raise CatalogPermissionConfigurationError(
            "A default Wagtail Site is required before catalogue permissions "
            "can be configured."
        ) from exc
    except Site.MultipleObjectsReturned as exc:
        raise CatalogPermissionConfigurationError(
            "Exactly one default Wagtail Site is required."
        ) from exc


def _get_or_create_catalog_root():
    site = _get_default_site()
    catalogues = list(CatalogIndexPage.objects.all())
    if len(catalogues) > 1:
        raise CatalogPermissionConfigurationError(
            "More than one catalogue index exists; resolve the page tree before "
            "configuring permissions."
        )

    if catalogues:
        catalogue = catalogues[0]
        if not catalogue.path.startswith(site.root_page.path):
            raise CatalogPermissionConfigurationError(
                "The catalogue index must be inside the default Wagtail Site page tree."
            )
        return catalogue, False

    parent = site.root_page.specific
    if not CatalogIndexPage.can_create_at(parent):
        raise CatalogPermissionConfigurationError(
            "The default Wagtail Site root does not allow a catalogue index child."
        )

    catalogue = CatalogIndexPage(
        title="Jewellery catalogue",
        slug="jewellery",
        intro="Explore jewellery available for enquiry at our Vellore showroom.",
        live=False,
        show_in_menus=False,
    )
    parent.add_child(instance=catalogue)
    catalogue.save_revision()
    return catalogue, True


def _get_or_create_media_collection():
    root = Collection.get_first_root_node()
    if root is None:
        root = Collection.add_root(name="Root")
    collection = root.get_children().filter(name=CATALOG_MEDIA_COLLECTION).first()
    if collection is None:
        collection = root.add_child(name=CATALOG_MEDIA_COLLECTION)
        return collection, True
    return collection, False


def _configure_group(role, catalogue, media_collection):
    group, created = Group.objects.get_or_create(name=role.name)
    group.permissions.set(
        [
            _permission(app_label, codename)
            for app_label, codename in role.model_permissions
        ]
    )

    GroupPagePermission.objects.filter(group=group).delete()
    for codename in role.page_permissions:
        GroupPagePermission.objects.create(
            group=group,
            page=catalogue,
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


def _configure_workflow(catalogue, publisher_group, administrator_group):
    tasks = list(GroupApprovalTask.objects.filter(name=CATALOG_REVIEW_TASK))
    if len(tasks) > 1:
        raise CatalogPermissionConfigurationError(
            "Multiple catalogue publisher approval tasks exist."
        )
    task_created = not tasks
    task = (
        tasks[0]
        if tasks
        else GroupApprovalTask.objects.create(name=CATALOG_REVIEW_TASK, active=True)
    )
    if not task.active:
        task.active = True
        task.save(update_fields=["active"])
    task.groups.set([publisher_group, administrator_group])

    workflows = list(Workflow.objects.filter(name=CATALOG_WORKFLOW))
    if len(workflows) > 1:
        raise CatalogPermissionConfigurationError(
            "Multiple catalogue review workflows exist."
        )
    workflow_created = not workflows
    workflow = (
        workflows[0]
        if workflows
        else Workflow.objects.create(name=CATALOG_WORKFLOW, active=True)
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
            raise CatalogPermissionConfigurationError(
                "The catalogue workflow has active submissions and cannot be reconciled safely."
            )
        WorkflowTask.objects.filter(workflow=workflow).delete()
        WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)

    WorkflowPage.objects.update_or_create(
        page=catalogue,
        defaults={"workflow": workflow},
    )
    return workflow, task, workflow_created, task_created


@transaction.atomic
def configure_catalog_permissions():
    catalogue, catalogue_created = _get_or_create_catalog_root()
    media_collection, collection_created = _get_or_create_media_collection()

    groups = {}
    created_groups = []
    for role in CATALOG_ROLES:
        group, created = _configure_group(role, catalogue, media_collection)
        groups[role.name] = group
        if created:
            created_groups.append(role.name)

    workflow, task, workflow_created, task_created = _configure_workflow(
        catalogue,
        groups[CATALOG_PUBLISHER_GROUP],
        groups[CATALOG_ADMIN_GROUP],
    )

    return {
        "catalogue": catalogue,
        "catalogue_created": catalogue_created,
        "media_collection": media_collection,
        "collection_created": collection_created,
        "groups": groups,
        "created_groups": created_groups,
        "workflow": workflow,
        "workflow_created": workflow_created,
        "task": task,
        "task_created": task_created,
    }


def catalog_permission_configuration_errors():
    errors = []
    try:
        site = _get_default_site()
    except CatalogPermissionConfigurationError as exc:
        return [str(exc)]

    catalogues = list(CatalogIndexPage.objects.all())
    if len(catalogues) != 1:
        return ["Exactly one catalogue index must exist."]
    catalogue = catalogues[0]
    if not catalogue.path.startswith(site.root_page.path):
        errors.append("The catalogue index is outside the default Site page tree.")

    root_collection = Collection.get_first_root_node()
    media_collection = None
    if root_collection is not None:
        media_collection = root_collection.get_children().filter(
            name=CATALOG_MEDIA_COLLECTION
        ).first()
    if media_collection is None:
        errors.append("The dedicated catalogue media collection is missing.")

    groups = {}
    for role in CATALOG_ROLES:
        try:
            group = Group.objects.get(name=role.name)
        except Group.DoesNotExist:
            errors.append(f"Group {role.name!r} is missing.")
            continue
        groups[role.name] = group

        if group.user_set.filter(is_staff=False).exists():
            errors.append(f"Group {role.name!r} contains a non-staff user.")

        actual_model_permissions = set(
            group.permissions.values_list("content_type__app_label", "codename")
        )
        if actual_model_permissions != set(role.model_permissions):
            errors.append(f"Group {role.name!r} has incorrect model permissions.")

        actual_page_permissions = set(
            GroupPagePermission.objects.filter(group=group, page=catalogue).values_list(
                "permission__codename", flat=True
            )
        )
        all_page_permission_count = GroupPagePermission.objects.filter(
            group=group
        ).count()
        if (
            actual_page_permissions != set(role.page_permissions)
            or all_page_permission_count != len(role.page_permissions)
        ):
            errors.append(f"Group {role.name!r} has incorrect page permissions.")

        if media_collection is not None:
            actual_image_permissions = set(
                GroupCollectionPermission.objects.filter(
                    group=group,
                    collection=media_collection,
                ).values_list("permission__codename", flat=True)
            )
            all_collection_permission_count = GroupCollectionPermission.objects.filter(
                group=group
            ).count()
            if (
                actual_image_permissions != set(role.image_permissions)
                or all_collection_permission_count != len(role.image_permissions)
            ):
                errors.append(f"Group {role.name!r} has incorrect media permissions.")

    try:
        workflow = Workflow.objects.get(name=CATALOG_WORKFLOW, active=True)
    except Workflow.DoesNotExist:
        errors.append("The active catalogue review workflow is missing.")
        return errors
    except Workflow.MultipleObjectsReturned:
        errors.append("Multiple active catalogue review workflows exist.")
        return errors

    try:
        task = GroupApprovalTask.objects.get(name=CATALOG_REVIEW_TASK, active=True)
    except GroupApprovalTask.DoesNotExist:
        errors.append("The active catalogue publisher approval task is missing.")
        return errors
    except GroupApprovalTask.MultipleObjectsReturned:
        errors.append("Multiple active catalogue publisher approval tasks exist.")
        return errors

    expected_reviewer_ids = {
        groups[name].pk
        for name in (CATALOG_PUBLISHER_GROUP, CATALOG_ADMIN_GROUP)
        if name in groups
    }
    if set(task.groups.values_list("pk", flat=True)) != expected_reviewer_ids:
        errors.append("The catalogue approval task has incorrect reviewer groups.")

    workflow_task_ids = list(
        WorkflowTask.objects.filter(workflow=workflow)
        .order_by("sort_order", "pk")
        .values_list("task_id", flat=True)
    )
    if workflow_task_ids != [task.pk]:
        errors.append("The catalogue review workflow has incorrect tasks.")

    if not WorkflowPage.objects.filter(page=catalogue, workflow=workflow).exists():
        errors.append(
            "The catalogue review workflow is not assigned to the catalogue root."
        )

    return errors
