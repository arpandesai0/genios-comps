"""Append-only experiment log for the evals (``experiments.jsonl``).

One JSON line per run of ``run.py``. The **experiment number** identifies a run; the commit is only
metadata, since one commit can be run with several settings (e.g. three embedding models). Each entry
records when it ran, what it tests, the commit and service settings, the hashes of every input and
golden file, where the captured pipeline output is and its hash, start-up time and memory, and the
scores. Lines are never rewritten or removed; a wrong run is corrected by a later one that says so.

    .venv/bin/python eval/experiments.py      # the log as a table

Entry 1 predates the black-box runner (schema 1: the eval imported the pipeline). Its fields differ,
and the table reads both.
"""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LOG = HERE / "experiments.jsonl"
SCHEMA = 2
METRICS = ("ndcg@5", "ndcg@10", "precision@10", "recall@10")


def read(log: Path | None = None) -> list[dict]:
    log = log or LOG
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def next_number(log: Path | None = None) -> int:
    entries = read(log)
    return entries[-1]["experiment"] + 1 if entries else 1


def _version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def record(
    *,
    number: int,
    description: str,
    commit: str,
    settings: Mapping[str, str],
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    runtime: Mapping[str, Any],
    results: Mapping[str, Any],
    log: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Append one experiment. ``number`` must be the next number (``next_number``)."""
    log = log or LOG
    if not description.strip():
        raise ValueError("an experiment needs a description of what it tests")
    if number != next_number(log):
        raise ValueError(f"experiment {number} is not next ({next_number(log)}): was another run logged meanwhile?")
    entry = {
        "experiment": number,
        "schema": SCHEMA,
        "date": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "description": description.strip(),
        "commit": commit,
        "settings": dict(settings),
        "env": {
            "python": platform.python_version(),
            **{p: _version(p) for p in ("numpy", "scikit-learn", "fastembed", "onnxruntime")},
        },
        "inputs": dict(inputs),
        "outputs": dict(outputs),
        "runtime": dict(runtime),
        "results": dict(results),
    }
    text = log.read_text() if log.exists() else ""
    with log.open("a") as f:
        f.write(("\n" if text and not text.endswith("\n") else "") + json.dumps(entry) + "\n")
    return entry


def _rows(e: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """One table row per (experiment, fixture): dev retrieval scores, or dev dedup recall."""
    if e.get("schema", 1) == 1:
        o, i = e["results"]["overall"], e["inputs"]
        cfg = f"{i['method']['name']} v{i['method']['version']}"
        nums = tuple(f"{o[m]:.3f}" for m in METRICS) + ("",)
        return [
            (
                str(e["experiment"]),
                e["date"][:10],
                (e["git"]["commit"] or "?")[:7],
                cfg,
                "retrieval_v1",
                *nums,
                e["description"],
            )
        ]
    cfg = e["settings"].get("EMBEDDING_MODEL", "(commit default)")
    rows = []
    for fixture, by_split in e["results"].items():
        dev = by_split.get("dev", {})
        if "overall" in dev:
            nums = tuple(f"{dev['overall'][m]:.3f}" for m in METRICS) + ("",)
        else:
            r = dev.get("recall_at_zero_false_duplicates")
            nums = ("", "", "", "", "" if r is None else f"{r:.3f}")
        rows.append((str(e["experiment"]), e["date"][:10], e["commit"][:7], cfg, fixture, *nums, e["description"]))
    return rows


def table(entries: Sequence[Mapping[str, Any]]) -> str:
    head = (
        "#",
        "date",
        "commit",
        "config",
        "fixture",
        "nDCG@5",
        "nDCG@10",
        "P@10",
        "R@10",
        "dedup R@0FP",
        "description",
    )
    rows = [head] + [r for e in entries for r in _rows(e)]
    widths = [max(len(r[c]) for r in rows) for c in range(len(head) - 1)]
    return "\n".join("  ".join(r[c].ljust(widths[c]) for c in range(len(widths))) + "  " + r[-1] for r in rows)


if __name__ == "__main__":
    print(table(read()))
    print("\nDev split. dedup R@0FP = duplicate recall at the strictest cut that flags no non-duplicate.")
    sys.exit(0)
