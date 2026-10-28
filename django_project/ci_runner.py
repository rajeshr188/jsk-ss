"""Opt-in CI runner: standard Django semantics, serial classes per isolated job."""
import json
import os
from pathlib import Path
import time
import unittest

from django.test.runner import DiscoverRunner, iter_test_cases
from django.test import TestCase, TransactionTestCase

from .ci_inventory import REPORT_VERSION, SHARD_COUNT, make_plan


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed = []
        self.case_durations = []

    def startTest(self, test):
        self.executed.append(test.id())
        self._case_started = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        self.case_durations.append(dict(id=test.id(), seconds=time.perf_counter() - self._case_started))
        super().stopTest(test)


class CiRunner(DiscoverRunner):
    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)
        parser.add_argument("--ci-shard", type=int)
        parser.add_argument("--ci-shards", type=int, default=SHARD_COUNT)
        parser.add_argument("--ci-report-dir", default=".ci-reports")
        parser.add_argument("--ci-plan-only", action="store_true")

    def __init__(self, *, ci_shard=None, ci_shards=SHARD_COUNT, ci_report_dir=".ci-reports",
                 ci_plan_only=False, **kwargs):
        super().__init__(**kwargs)
        if type(ci_shards) is not int or ci_shards < 1 or (ci_shard is not None and type(ci_shard) is not int):
            raise ValueError("CI shard indices and counts must be integers.")
        if self.parallel > 1 or self.failfast or self.shuffle is not False or self.reverse:
            raise ValueError("CI shards must keep serial, complete, deterministic Django execution.")
        if ci_shard is not None and not 0 <= ci_shard < ci_shards:
            raise ValueError("The CI shard index must be within the planned shard count.")
        self.ci_shard, self.ci_shards = ci_shard, ci_shards
        self.ci_plan_only, self.report_dir = ci_plan_only, Path(ci_report_dir)
        self.revision = os.environ.get("GITHUB_SHA", "local")

    def build_suite(self, test_labels=None, **kwargs):
        if self.ci_plan_only or self.ci_shard is not None:
            if ((test_labels and list(test_labels) != ["."]) or self.tags
                    or self.exclude_tags or self.test_name_patterns
                    or self.pattern not in (None, "test*.py") or self.top_level is not None):
                raise ValueError("CI inventory discovery must not be narrowed by labels, tags or patterns.")
        suite = super().build_suite(test_labels, **kwargs)
        cases = list(iter_test_cases(suite))
        if any(isinstance(test, unittest.loader._FailedTest) for test in cases):
            raise ValueError("Test discovery failed; refusing an incomplete CI inventory.")
        # Local targeted profiling is supported without pretending it is full CI.
        shards = self.ci_shards if self.ci_plan_only or self.ci_shard is not None else 1
        transactions = {f"{type(test).__module__}.{type(test).__qualname__}" for test in cases
                        if isinstance(test, TransactionTestCase) and not isinstance(test, TestCase)}
        self.plan = make_plan([test.id() for test in cases], shards=shards, revision=self.revision,
                              transaction_classes=transactions)
        if self.ci_plan_only:
            self._write("plan.json", self.plan)
            self.log(f"Planned {len(cases)} tests across {shards} isolated serial shards: "
                     + ", ".join(str(len(group)) for group in self.plan["assignments"]))
            return suite
        self.selected = self.plan["assignments"][self.ci_shard or 0]
        selected = set(self.selected)
        # Filter the standard ordered suite; never reorder methods or split fixtures.
        return self.test_suite(test for test in cases if test.id() in selected)

    def _write(self, filename, data):
        self.report_dir.mkdir(parents=True, exist_ok=True)
        (self.report_dir / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def run_tests(self, test_labels, **kwargs):
        if self.ci_plan_only:
            self.build_suite(test_labels)
            return 0
        return super().run_tests(test_labels, **kwargs)

    def get_resultclass(self):
        return TimedResult

    def run_suite(self, suite, **kwargs):
        started = time.perf_counter()
        result = super().run_suite(suite, **kwargs)
        report = dict(version=REPORT_VERSION, revision=self.revision, shard=self.ci_shard,
            fingerprint=self.plan["fingerprint"], planned=self.selected, executed=result.executed,
            tests_run=result.testsRun, successful=result.wasSuccessful(),
            suite_seconds=time.perf_counter() - started, durations=result.case_durations)
        self._write(f"shard-{self.ci_shard}.json" if self.ci_shard is not None else "profile.json", report)
        return result
