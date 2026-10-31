"""Stdlib-only infrastructure tests also run in the cheap scope job."""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest
from unittest.mock import patch

from django_project.ci_scope import changed_paths, prose_path, require_validation, validate_prose, validation_mode


class CiScopeTests(unittest.TestCase):
    def test_prose_changes_have_an_explicit_lightweight_path(self):
        for event in ("push", "pull_request"):
            self.assertEqual(validation_mode(["docs/STATUS.md", "README.md"], event=event), "docs")
        self.assertEqual(validation_mode(["docs/decisions/ADR-0017.md"], event="pull_request"), "docs")

    def test_runtime_handbook_assets_build_financial_and_unknown_paths_need_every_test(self):
        for name in ("docs/guides/plan-configuration/index.html", "docs/guides/plan-configuration/assets/a.jpg",
                     "docs/guides/plan-configuration/source.md",
                     "schemes/services.py", "accounts/models.py", "templates/home.html", "Dockerfile",
                     ".github/workflows/ci.yml", "django_project/ci_scope.py", "uv.lock",
                     "compose.production.yml", "new-unknown-file", "../docs/STATUS.md", "/docs/a.md"):
            with self.subTest(name=name):
                self.assertEqual(validation_mode(["docs/STATUS.md", name], event="pull_request"), "full")
        self.assertEqual(validation_mode([], event="push"), "full")
        self.assertEqual(validation_mode(["docs/STATUS.md"], event="workflow_dispatch"), "full")
        with self.assertRaises(ValueError): validation_mode([], event="unknown")

    def test_paths_are_nul_delimited_no_shell_and_rename_deletions_cannot_hide_code(self):
        with patch("subprocess.check_output", return_value=b"schemes/old.py\0docs/new.md\0") as diff:
            names = changed_paths("base-ref", "head-ref")
        self.assertEqual(names, ["schemes/old.py", "docs/new.md"])
        self.assertIn("--no-renames", diff.call_args.args[0])
        self.assertEqual(validation_mode(names, event="pull_request"), "full")
        with patch("subprocess.check_output") as diff:
            self.assertEqual(changed_paths("0" * 40, "head"), [])
            diff.assert_not_called()

    def test_deleted_or_utf8_prose_is_valid_but_binary_and_runtime_paths_are_not(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "README.md").write_text("Readable documentation", encoding="utf-8")
            validate_prose(root, ["README.md", "docs/deleted.md"])
            (root / "README.md").write_bytes(b"bad\x00text")
            with self.assertRaises(ValueError): validate_prose(root, ["README.md"])
            with self.assertRaises(ValueError): validate_prose(root, ["Dockerfile"])

    def test_required_gate_never_accepts_missing_scope_or_failed_incomplete_runtime_tests(self):
        self.assertIn("Documentation-only", require_validation(scope_result="success", mode="docs",
            checks_result="skipped", tests_result="skipped"))
        self.assertIn("Full application", require_validation(scope_result="success", mode="full",
            checks_result="success", tests_result="success"))
        for changes in ({"scope_result": "failure"}, {"scope_result": "skipped"},
                        {"tests_result": "failure"}, {"tests_result": "cancelled"},
                        {"tests_result": "skipped"}, {"checks_result": "skipped"}, {"mode": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                require_validation(**(dict(scope_result="success", mode="full",
                    checks_result="success", tests_result="success") | changes))

    def test_actual_git_diff_recognises_prose_and_does_not_hide_runtime_renames(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            git("config", "user.name", "Synthetic CI scope test")
            git("config", "user.email", "scope@example.invalid")
            (root / "README.md").write_text("Initial prose\n")
            (root / "Dockerfile").write_text("FROM scratch\n")
            git("add", "."); git("commit", "-m", "Synthetic base")
            base = git("rev-parse", "HEAD")
            (root / "README.md").write_text("Updated prose\n")
            git("add", "."); git("commit", "-m", "Synthetic docs")
            docs = git("rev-parse", "HEAD")
            self.assertEqual(validation_mode(changed_paths(base, docs, cwd=root), event="pull_request"), "docs")
            (root / "docs").mkdir()
            git("mv", "Dockerfile", "docs/former.md")
            git("commit", "-m", "Synthetic code rename")
            head = git("rev-parse", "HEAD")
            self.assertEqual(validation_mode(changed_paths(docs, head, cwd=root), event="push"), "full")


if __name__ == "__main__":
    unittest.main()
