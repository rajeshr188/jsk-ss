from django.core.management.base import BaseCommand, CommandError

from catalog.permissions import (
    CatalogPermissionConfigurationError,
    catalog_permission_configuration_errors,
    configure_catalog_permissions,
)


class Command(BaseCommand):
    help = (
        "Create or reconcile the bounded catalogue CMS groups, page/media scope, "
        "and publisher approval workflow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Validate the catalogue CMS authorization configuration without "
                "changing it."
            ),
        )

    def handle(self, *args, **options):
        if options["check"]:
            errors = catalog_permission_configuration_errors()
            if errors:
                raise CommandError(
                    "Catalogue authorization check failed: " + " ".join(errors)
                )
            self.stdout.write(
                self.style.SUCCESS(
                    "Catalogue authorization configuration is valid."
                )
            )
            return

        try:
            result = configure_catalog_permissions()
        except CatalogPermissionConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        created = []
        if result["catalogue_created"]:
            created.append("draft catalogue root")
        if result["collection_created"]:
            created.append("catalogue media collection")
        created.extend(result["created_groups"])
        if result["task_created"]:
            created.append("publisher approval task")
        if result["workflow_created"]:
            created.append("catalogue review workflow")

        detail = ", ".join(created) if created else "no new objects"
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue authorization configured ({detail}). "
                "Assign staff users to a catalogue group explicitly; application "
                "roles are unchanged."
            )
        )
