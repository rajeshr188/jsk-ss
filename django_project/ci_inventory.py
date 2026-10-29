"""Pure CI inventory partition/verification; no application settings or database access."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


SHARD_COUNT = 4
REPORT_VERSION = 1


def make_plan(test_ids, *, shards=SHARD_COUNT, revision="local", transaction_classes=()):
    ids = list(test_ids)
    if any(not isinstance(value, str) or "." not in value for value in ids):
        raise ValueError("Every discovered test needs a fully qualified identity.")
    ids.sort()
    if type(shards) is not int or shards < 1 or not ids or len(ids) != len(set(ids)):
        raise ValueError("A nonempty unique test inventory and positive shard count are required.")
    classes = defaultdict(list)
    for test_id in ids:
        classes[test_id.rsplit(".", 1)[0]].append(test_id)
    transaction_classes = sorted(set(transaction_classes))
    if not set(transaction_classes).issubset(classes):
        raise ValueError("Transactional classes must belong to the discovered inventory.")
    # Spread costly transactional fixtures first, then fill with regular classes.
    # This is a deterministic bootstrap heuristic, not a claimed runtime estimate.
    assignments = [[] for _ in range(shards)]
    for _, members in sorted(classes.items(), key=lambda item:
            (item[0] not in transaction_classes, -len(item[1]), item[0])):
        target = min(range(shards), key=lambda i: (len(assignments[i]), i))
        assignments[target].extend(members)
    if any(not group for group in assignments):
        raise ValueError("Every shard must contain at least one complete test class.")
    plan = dict(version=REPORT_VERSION, revision=revision, inventory=ids, transaction_classes=transaction_classes,
                assignments=[sorted(group) for group in assignments])
    plan["fingerprint"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return plan


def verify_reports(plan, reports, *, revision=None):
    # Recompute the authoritative partition rather than trusting its JSON digest.
    expected = make_plan(plan["inventory"], shards=len(plan["assignments"]), revision=plan["revision"],
                         transaction_classes=plan["transaction_classes"])
    if plan != expected or (revision is not None and plan["revision"] != revision):
        raise ValueError("The test plan does not match this revision or deterministic inventory.")
    if len(reports) != len(plan["assignments"]):
        raise ValueError("A successful report from every planned shard is required.")
    seen, executed = set(), []
    for report in reports:
        index = report["shard"]
        if type(index) is not int or not 0 <= index < len(plan["assignments"]) or index in seen:
            raise ValueError("Missing, duplicate or unexpected test shard.")
        seen.add(index)
        assigned = plan["assignments"][index]
        actual = report["executed"]
        if (report.get("version") != REPORT_VERSION or report.get("revision") != plan["revision"]
                or report.get("fingerprint") != plan["fingerprint"]
                or report.get("planned") != assigned or report.get("successful") is not True
                or Counter(actual) != Counter(assigned) or report.get("tests_run") != len(assigned)):
            raise ValueError(f"Shard {index} failed or did not execute its exact planned inventory.")
        executed.extend(actual)
    if Counter(executed) != Counter(plan["inventory"]):
        raise ValueError("Combined shards must execute every discovered test exactly once.")
    return len(executed)


def verify_directory(directory, *, revision=None):
    directory = Path(directory)
    plans = list(directory.rglob("plan.json"))
    if len(plans) != 1:
        raise ValueError("Exactly one authoritative discovery plan is required.")
    plan = json.loads(plans[0].read_text(encoding="utf-8"))
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.rglob("shard-*.json"))]
    count = verify_reports(plan, reports, revision=revision)
    print(f"CI inventory verified: {count} tests, {len(reports)} isolated shards, no omissions or duplicates.")
    slowest = sorted((row for report in reports for row in report["durations"]),
                     key=lambda row: row["seconds"], reverse=True)[:30]
    print("Slowest unittest executions (setUp/tearDown included; Django outer fixture/database overhead excluded):")
    for row in slowest:
        print(f"{row['seconds']:9.3f}s {row['id']}")
    for report in sorted(reports, key=lambda row: row["shard"]):
        case_seconds = sum(row["seconds"] for row in report["durations"])
        print(f"Shard {report['shard']}: {report['tests_run']} tests, suite {report['suite_seconds']:.3f}s, "
              f"unittest execution {case_seconds:.3f}s; database setup/teardown is in Django --timing logs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    verify_directory(args.directory, revision=args.revision)
