from django.core.management.base import BaseCommand, CommandError

from blog.permissions import (
    blog_permission_configuration_errors,
    configure_blog_permissions,
)


class Command(BaseCommand):
    help = (
        "Create or reconcile the bounded blog groups, page/media scope, draft root, "
        "and approval workflow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Validate blog authorization without changing data.",
        )

    def handle(self, *args, **options):
        if options["check"]:
            errors = blog_permission_configuration_errors()
            if errors:
                raise CommandError(" ".join(errors))
            self.stdout.write(self.style.SUCCESS("Blog authorization is valid."))
            return

        result = configure_blog_permissions()
        created = []
        if result["blog_created"]:
            created.append("draft blog root")
        if result["collection_created"]:
            created.append("blog media collection")
        created.extend(result["created_groups"])
        if result["task_created"]:
            created.append("publisher approval task")
        if result["workflow_created"]:
            created.append("blog review workflow")
        detail = ", ".join(created) if created else "no new objects"
        self.stdout.write(
            self.style.SUCCESS(
                "Blog authorization configured "
                f"({detail}). Assign staff users to a Blog group explicitly; "
                "application roles are unchanged."
            )
        )
