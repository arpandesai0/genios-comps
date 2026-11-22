"""Append-only experiment log for the evals.

Each eval run started with ``--log "description"`` appends one JSON line to ``experiments.jsonl``:
the experiment number, when it ran, what it was meant to test, the git commit it ran on, its inputs
(method, fixture and label versions, split, settings, library versions) and its headline metrics. Lines
are never rewritten or removed; a wrong run is corrected by a later one whose description says so.

    make experiment DESC="what this run tests"      # dev split, appends to the log
    .venv/bin/python eval/experiments.py            # print the log as a table

The full per-target result stays in ``results/`` (``--out``); the log keeps the history.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOG = HERE / "experiments.jsonl"
# Paths whose uncommitted changes can change a result. Outputs (the log and the result file the run
# writes) are excluded.
RESULT_INPUTS = ("src", "eval", "pyproject.toml", "requirements.lock")


def _git(root: Path, *args: str) -> str | None:
    """Output of a git command, or None if git is missing or fails (not a repo, dubious ownership)."""
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout


def git_info(root: Path = ROOT, outputs: Sequence[Path] = ()) -> dict:
    """The commit the run used, and whether files that affect results had uncommitted changes.

    Every field is None when git can't answer, so "unknown" is never recorded as "clean". ``outputs``
    are files this run writes; they don't make the tree dirty.
    """
    root = root.resolve()
    ignored = {_repo_path(p, root) for p in (LOG, *outputs)}
    status = _git(root, "status", "--porcelain", "-z", "--", *RESULT_INPUTS)
    commit = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    changed: list[str] | None = None
    if status is not None:
        changed, fields = [], iter(status.split("\0"))
        for field in fields:
            if not field:
                continue
            code, path = field[:2], field[3:]
            if code[0] in "RC":  # renames and copies carry the original path in the next field
                next(fields, None)
            if path not in ignored:
                changed.append(path)
    return {
        "commit": commit.strip() if commit else None,
        "branch": None if branch is None or branch.strip() == "HEAD" else branch.strip(),  # None when detached
        "dirty": None if changed is None else bool(changed),
        "dirty_paths": None if changed is None else sorted(changed),
    }


def _repo_path(path: Path, root: Path = ROOT) -> str:
    """``path`` relative to the repo as git prints it, or absolute if it lies outside the repo."""
    resolved = path.resolve()
    return resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else resolved.as_posix()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def read(log: Path | None = None) -> list[dict]:
    log = log or LOG
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def record(
    result: Mapping,
    *,
    description: str,
    eval_name: str,
    inputs: Mapping,
    result_file: Path | None = None,
    log: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Append one experiment to ``log`` and return it. The number is one more than the last entry.

    The log is written by one person at a time from a local checkout, so there is no lock.
    """
    if not description.strip():
        raise ValueError("an experiment needs a description of what it tests")
    log = log or LOG
    entries = read(log)
    entry = {
        "experiment": (entries[-1]["experiment"] + 1) if entries else 1,
        "date": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "description": description.strip(),
        "eval": eval_name,
        "git": git_info(outputs=[result_file] if result_file else ()),
        "inputs": {
            **inputs,
            "env": {
                "python": platform.python_version(),
                "numpy": version("numpy"),
                "scikit-learn": version("scikit-learn"),
            },
        },
        "results": {
            "targets": result["targets"],
            "overall": result["overall"],
            "by_tag": result["by_tag"],
            "duplicate_listing_returned": result["duplicate_listing_returned"],
            "geography_lift": result["geography"]["lift"],
        },
        # The result file is overwritten by later runs; its hash tells whether it still holds this run.
        "result_file": _repo_path(result_file) if result_file else None,
        "result_sha": file_hash(result_file) if result_file else None,
    }
    text = log.read_text() if log.exists() else ""
    with log.open("a") as f:
        f.write(("\n" if text and not text.endswith("\n") else "") + json.dumps(entry) + "\n")
    return entry


def table(entries: Sequence[Mapping]) -> str:
    head = ("#", "date", "commit", "method", "split", "nDCG@5", "nDCG@10", "P@10", "R@10", "description")
    rows = [head]
    for e in entries:
        o, i = e["results"]["overall"], e["inputs"]
        dirty = {True: "*", None: "?", False: ""}[e["git"]["dirty"]]
        commit = (e["git"]["commit"] or "?")[:7] + dirty
        method = f"{i['method']['name']} v{i['method']['version']}"
        metrics = (o.get("ndcg@5"), o.get("ndcg@10"), o.get("precision@10"), o.get("recall@10"))
        rows.append(
            (str(e["experiment"]), e["date"][:10], commit, method, i["split"])
            + tuple("" if m is None else f"{m:.3f}" for m in metrics)
            + (e["description"],)
        )
    widths = [max(len(r[c]) for r in rows) for c in range(len(head) - 1)]
    return "\n".join("  ".join(r[c].ljust(widths[c]) for c in range(len(widths))) + "  " + r[-1] for r in rows)


if __name__ == "__main__":
    print(table(read()) + "\n\n* = uncommitted changes to files that affect results; ? = git state unknown")
    sys.exit(0)
