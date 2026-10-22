from unittest.mock import patch

from django.test import SimpleTestCase

from schemes.rehearse_workflow_release import main, validate_database


class WorkflowReleaseIsolationTests(SimpleTestCase):
    def test_no_flag_or_custom_database_arguments_are_rejected_before_setup(self):
        for arguments in ([], ["--database", "production"], ["--synthetic-local", "extra"]):
            with (
                self.subTest(arguments=arguments),
                patch("sys.argv", ["rehearsal", *arguments]),
                patch("django.setup") as setup,
                self.assertRaisesRegex(RuntimeError, "Explicit"),
            ):
                main()
            setup.assert_not_called()

    def test_only_explicit_local_postgres_without_options_is_accepted(self):
        local = {"ENGINE": "django.db.backends.postgresql", "HOST": "127.0.0.1", "OPTIONS": {}}
        validate_database(local)
        for changes in ({"HOST": "production.example.invalid"}, {"HOST": ""},
                        {"ENGINE": "django.db.backends.sqlite3"},
                        {"OPTIONS": {"service": "another-database"}},
                        {"OPTIONS": {"host": "production.example.invalid"}}):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                validate_database({**local, **changes})
