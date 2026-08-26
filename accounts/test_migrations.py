from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CustomerInvitationMigrationTests(TransactionTestCase):
    migrate_from = ("accounts", "0002_customuser_role")
    migrate_to = ("accounts", "0003_customerinvitation_and_more")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.old_apps = executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.migrate_to])
        super().tearDown()

    def test_duplicate_case_insensitive_emails_stop_before_constraint(self):
        user_model = self.old_apps.get_model("accounts", "CustomUser")
        user_model.objects.create(
            username="migration-first@example.com",
            email="Duplicate@Example.com",
            password="!",
            role="CUSTOMER",
        )
        duplicate = user_model.objects.create(
            username="migration-second@example.com",
            email="duplicate@example.com",
            password="!",
            role="CUSTOMER",
        )

        with self.assertRaisesMessage(
            RuntimeError,
            "duplicate nonblank case-insensitive email groups exist",
        ):
            MigrationExecutor(connection).migrate([self.migrate_to])

        duplicate.delete()
        MigrationExecutor(connection).migrate([self.migrate_to])
