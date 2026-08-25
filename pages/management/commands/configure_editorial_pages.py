from django.core.management.base import BaseCommand, CommandError

from pages.permissions import (
    EditorialPermissionConfigurationError,
    configure_editorial_pages,
    editorial_permission_configuration_errors,
)


class Command(BaseCommand):
    help = (
        "Create or reconcile draft About/Our Story pages, dedicated editorial "
        "authorization, media scope, and publisher approval workflow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Validate editorial CMS configuration without changing it.",
        )

    def handle(self, *args, **options):
        if options["check"]:
            errors = editorial_permission_configuration_errors()
            if errors:
                raise CommandError(
                    "Editorial authorization check failed: " + " ".join(errors)
                )
            self.stdout.write(
                self.style.SUCCESS("Editorial CMS configuration is valid.")
            )
            return

        try:
            result = configure_editorial_pages()
        except EditorialPermissionConfigurationError as exc:
            raise CommandError(str(exc)) from exc

        created = []
        page_names = ("draft About page", "draft Our Story page")
        created.extend(
            name
            for name, was_created in zip(page_names, result["created_pages"])
            if was_created
        )
        if result["collection_created"]:
            created.append("editorial media collection")
        created.extend(result["created_groups"])
        if result["task_created"]:
            created.append("publisher approval task")
        if result["workflow_created"]:
            created.append("editorial review workflow")
        detail = ", ".join(created) if created else "no new objects"
        self.stdout.write(
            self.style.SUCCESS(
                f"Editorial CMS configured ({detail}). Assign staff users to an "
                "Editorial group explicitly; application roles are unchanged."
            )
        )
