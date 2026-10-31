"""Conservative CI scope: unknown/runtime/build changes always need full validation.

Only prose Markdown under docs/, README.md and AGENTS.md can use the lightweight
path. The served HTML handbook, assets, deployment files and CI code are runtime
changes. Workflow-level path filters are deliberately avoided so required checks
can report an explicit, verified documentation-only outcome.
"""
import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess


def prose_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        return False
    if name.startswith("docs/guides/"):
        return False  # The owner handbook and its future sources are runtime assets.
    return name in {"README.md", "AGENTS.md"} or (
        name.startswith("docs/") and path.suffix == ".md"
    )


def validation_mode(names, *, event):
    names = list(names)
    if event == "workflow_dispatch":
        return "full"
    if event not in {"pull_request", "push"}:
        raise ValueError("Unknown CI event; do not infer a passing scope.")
    return "docs" if names and all(prose_path(name) for name in names) else "full"


def changed_paths(base, head, *, cwd=None):
    if not base or set(base) == {"0"}:
        return []  # Initial push or absent baseline requires the complete suite.
    # No shell interpolation; NUL delimiters preserve whitespace/newline filenames.
    output = subprocess.check_output([
        "git", "diff", "--no-renames", "--name-only", "-z", base, head, "--",
    ], cwd=cwd)
    return [name.decode("utf-8") for name in output.split(b"\0") if name]


def validate_prose(root, names):
    root = Path(root).resolve()
    for name in names:
        if not prose_path(name):
            raise ValueError("Documentation-only validation cannot accept runtime paths.")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Documentation paths must be regular files within the checkout.")
        if not path.exists():
            continue  # A documented deletion still belongs to this exact Git diff.
        text = path.read_text(encoding="utf-8-sig")
        if "\0" in text:
            raise ValueError("Documentation must be UTF-8 text without NUL bytes.")


def require_validation(*, scope_result, mode, checks_result, tests_result):
    if scope_result != "success":
        raise ValueError("Scope discovery/validation did not succeed.")
    if mode == "docs" and checks_result == tests_result == "skipped":
        return "Documentation-only validation passed; no application-suite or release-image claim."
    if mode == "full" and checks_result == tests_result == "success":
        return "Full application checks and every test shard passed."
    raise ValueError("Full validation is required: finish local work and mark a draft ready for review.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scope = commands.add_parser("scope")
    scope.add_argument("--base", default="")
    scope.add_argument("--head", required=True)
    scope.add_argument("--event", required=True)
    scope.add_argument("--output", required=True)
    commands.add_parser("gate")
    args = parser.parse_args()
    if args.command == "gate":
        print(require_validation(scope_result=os.environ["SCOPE_RESULT"],
            mode=os.environ["VALIDATION_MODE"], checks_result=os.environ["CHECKS_RESULT"],
            tests_result=os.environ["TESTS_RESULT"]))
        return
    paths = changed_paths(args.base, args.head)
    mode = validation_mode(paths, event=args.event)
    if mode == "docs":
        validate_prose(Path.cwd(), paths)
        subprocess.run(["git", "diff", "--check", args.base, args.head, "--"], check=True)
    with open(args.output, "a", encoding="utf-8") as output:
        output.write(f"mode={mode}\n")
    print(f"CI scope={mode}; changed paths={len(paths)}; complete suite required={mode == 'full'}")


if __name__ == "__main__":
    main()
