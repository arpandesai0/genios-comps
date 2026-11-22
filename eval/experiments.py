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

HERE = Path(__file__).parent
ROOT = HERE.parent
LOG = HERE / "experiments.jsonl"
# Paths whose uncommitted changes can change a result. The log itself is excluded.
RESULT_INPUTS = ("src", "eval", "pyproject.toml", "requirements.lock")


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.stdout.rstrip("\n")  # keep leading spaces: porcelain status codes use them


def git_info() -> dict:
    """The commit the run used, and whether files that affect results had uncommitted changes."""
    changed = [
        line[3:]
        for line in _git("status", "--porcelain", "--", *RESULT_INPUTS).splitlines()
        if line[3:] != str(LOG.relative_to(ROOT))
    ]
    return {
        "commit": _git("rev-parse", "HEAD") or None,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or None,
        "dirty": bool(changed),
        "dirty_paths": sorted(changed),
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def read(log: Path = LOG) -> list[dict]:
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
    log: Path = LOG,
    now: datetime | None = None,
) -> dict:
    """Append one experiment to ``log`` and return it. The number is one more than the last entry."""
    if not description.strip():
        raise ValueError("an experiment needs a description of what it tests")
    entries = read(log)
    entry = {
        "experiment": (entries[-1]["experiment"] + 1) if entries else 1,
        "date": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "description": description.strip(),
        "eval": eval_name,
        "git": git_info(),
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
        "result_file": str(result_file.resolve().relative_to(ROOT)) if result_file else None,
    }
    with log.open("a") as f:
        f.write(json.dumps(entry, sort_keys=False) + "\n")
    return entry


def table(entries: Sequence[Mapping]) -> str:
    head = ("#", "date", "commit", "method", "split", "nDCG@5", "nDCG@10", "P@10", "R@10", "description")
    rows = [head]
    for e in entries:
        o, i = e["results"]["overall"], e["inputs"]
        commit = (e["git"]["commit"] or "?")[:7] + ("*" if e["git"]["dirty"] else "")
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
    print(table(read()) + "\n\n* = uncommitted changes to files that affect results")
    sys.exit(0)
