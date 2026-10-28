"""CI must prove complete discovery/execution, even when jobs or reports fail."""
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner, iter_test_cases

from django_project.ci_inventory import make_plan, verify_reports, verify_directory
from django_project.ci_runner import CiRunner, TimedResult


class CiInventoryTests(SimpleTestCase):
    def setUp(self):
        self.ids = [f"sample.Case{i}.test_{j}" for i in range(8) for j in range(i + 1)]
        self.transactions = ["sample.Case0", "sample.Case3", "sample.Case7"]
        self.plan = make_plan(self.ids, shards=4, revision="synthetic-revision", transaction_classes=self.transactions)

    def reports(self):
        return [dict(version=1, revision=self.plan["revision"], shard=i,
            fingerprint=self.plan["fingerprint"], planned=ids, executed=list(reversed(ids)),
            successful=True, tests_run=len(ids), durations=[], suite_seconds=1.0)
            for i, ids in enumerate(self.plan["assignments"])]

    def test_partition_is_deterministic_complete_and_never_splits_class_fixtures(self):
        self.assertEqual(self.plan, make_plan(reversed(self.ids), shards=4, revision="synthetic-revision",
                                             transaction_classes=reversed(self.transactions)))
        self.assertCountEqual([test for group in self.plan["assignments"] for test in group], self.ids)
        owners = {}
        for index, group in enumerate(self.plan["assignments"]):
            for test in group:
                cls = test.rsplit(".", 1)[0]
                self.assertEqual(owners.setdefault(cls, index), index)
        self.assertEqual(verify_reports(self.plan, self.reports(), revision="synthetic-revision"), len(self.ids))
        self.assertEqual(self.plan["transaction_classes"], sorted(self.transactions))

    def test_invalid_discovery_cannot_produce_a_passing_plan(self):
        for ids, count in (([], 1), (["a.C.t", "a.C.t"], 1), ([None], 1), (["invalid"], 1),
                           (["a.C.t"], 0), (["a.C.t"], True), (["a.C.t"], 2)):
            with self.subTest(ids=ids, count=count), self.assertRaises(ValueError):
                make_plan(ids, shards=count)

    def test_missing_extra_duplicate_failed_or_incomplete_shards_fail_the_gate(self):
        mutations = [lambda rows: rows.pop(), lambda rows: rows.append(rows[0]),
            lambda rows: rows[0].update(shard=1), lambda rows: rows[0].update(shard=-1),
            lambda rows: rows[0].update(shard=True), lambda rows: rows[0].update(successful=False),
            lambda rows: rows[0].update(tests_run=0), lambda rows: rows[0]["executed"].pop(),
            lambda rows: rows[0]["executed"].append(rows[0]["executed"][0]),
            lambda rows: rows[0]["planned"].append("omitted.SomeCase.test_missing"),
            lambda rows: rows[0].update(revision="another-revision"),
            lambda rows: rows[0].update(fingerprint="wrong")]
        for mutate in mutations:
            reports = deepcopy(self.reports())
            mutate(reports)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                verify_reports(self.plan, reports)

    def test_stale_or_modified_authoritative_plan_cannot_approve_execution(self):
        with self.assertRaises(ValueError):
            verify_reports(self.plan, self.reports(), revision="stale-revision")
        changed = deepcopy(self.plan)
        changed["inventory"].append("extra.Case.test_not_run")
        with self.assertRaises(ValueError):
            verify_reports(changed, self.reports())

    def test_directory_verifier_requires_authoritative_plan_and_all_results(self):
        with TemporaryDirectory() as directory, patch("sys.stdout", new_callable=io.StringIO) as output:
            root = Path(directory)
            with self.assertRaises(ValueError):
                verify_directory(root)
            (root / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
            for report in self.reports():
                (root / f"shard-{report['shard']}.json").write_text(json.dumps(report), encoding="utf-8")
            verify_directory(root, revision="synthetic-revision")
            self.assertIn(f"{len(self.ids)} tests, 4 isolated shards", output.getvalue())


class CiRunnerTests(SimpleTestCase):
    def cases(self):
        # Keep synthetic TestCase types local so normal discovery never collects them.
        result = []
        for i in range(4):
            cls = type(f"Synthetic{i}", (unittest.TestCase,),
                {"test_one": lambda self: None, "test_two": lambda self: None})
            result.extend([cls("test_one"), cls("test_two")])
        return result

    def test_each_shard_filters_standard_order_without_splitting_or_omitting_tests(self):
        cases, selected = self.cases(), []
        with TemporaryDirectory() as directory, patch("sys.stderr", new_callable=io.StringIO), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            planner = CiRunner(ci_plan_only=True, ci_report_dir=directory)
            with patch.object(DiscoverRunner, "build_suite", return_value=unittest.TestSuite(cases)):
                planner.run_tests(())
            for index in range(4):
                runner = CiRunner(ci_shard=index, ci_shards=4, ci_report_dir=directory)
                with patch.object(DiscoverRunner, "build_suite", return_value=unittest.TestSuite(cases)):
                    subset = list(iter_test_cases(runner.build_suite([])))
                self.assertEqual(subset, [test for test in cases if test.id() in runner.selected])
                selected.extend(test.id() for test in subset)
                self.assertTrue(runner.run_suite(unittest.TestSuite(subset)).wasSuccessful())
            verify_directory(directory, revision=planner.revision)
            self.assertIn("8 tests, 4 isolated shards", output.getvalue())
        self.assertCountEqual(selected, [test.id() for test in cases])

    def test_discovery_only_writes_plan_without_database_or_suite_execution(self):
        with TemporaryDirectory() as directory:
            runner = CiRunner(ci_plan_only=True, ci_report_dir=directory)
            with patch.object(DiscoverRunner, "build_suite", return_value=unittest.TestSuite(self.cases())), \
                    patch.object(runner, "setup_databases", side_effect=AssertionError("No database for planning")):
                self.assertEqual(runner.run_tests(()), 0)  # Actual manage.py CLI supplies an empty tuple.
            self.assertEqual(len(json.loads((Path(directory) / "plan.json").read_text())["inventory"]), 8)

    def test_narrowed_filtered_parallel_or_failfast_ci_cannot_claim_full_coverage(self):
        for options in (dict(parallel=2), dict(failfast=True), dict(reverse=True), dict(shuffle=123),
                        dict(ci_shard=-1), dict(ci_shards=0)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CiRunner(**options)
        for options in (dict(tags=["some"]), dict(exclude_tags=["some"]), dict(test_name_patterns=["*one*"]),
                        dict(pattern="test_ci.py"), dict(top_level="partial_subdirectory")):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CiRunner(ci_shard=0, **options).build_suite([])
        with self.assertRaises(ValueError):
            CiRunner(ci_shard=0).build_suite(["sample.Case"])

    def test_profile_preserves_failure_and_records_success_failure_and_skip(self):
        cases = self.cases()[:1]
        failed = type("SyntheticFailure", (unittest.TestCase,),
            {"test_fail": lambda self: self.fail("Synthetic expected infrastructure test failure")})
        skipped = type("SyntheticSkip", (unittest.TestCase,),
            {"test_skip": unittest.skip("Synthetic existing skip")(lambda self: None)})
        cases += [failed("test_fail"), skipped("test_skip")]
        with TemporaryDirectory() as directory:
            runner = CiRunner(ci_report_dir=directory, verbosity=0)
            with patch.object(DiscoverRunner, "build_suite", return_value=unittest.TestSuite(cases)):
                suite = runner.build_suite(["targeted_local_profile"])
            with patch("sys.stderr", new_callable=io.StringIO):
                result = runner.run_suite(suite)
            self.assertFalse(result.wasSuccessful())
            report = json.loads((Path(directory) / "profile.json").read_text())
            self.assertFalse(report["successful"])
            self.assertEqual(report["tests_run"], 3)
            self.assertCountEqual(report["executed"], report["planned"])
            self.assertEqual(len(report["durations"]), 3)
            self.assertTrue(all(row["seconds"] >= 0 for row in report["durations"]))
