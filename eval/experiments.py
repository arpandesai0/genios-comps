"""Append-only experiment log for the evals (``experiments.json``).

A pretty-printed JSON array, one entry per run of ``run.py``. The **experiment number** identifies a
run; the commit is only metadata, since one commit can be run with several settings. Each entry
records when it ran, what it tests, the commit and service settings, the hashes of every input and
golden file, the model's vector size, where the captured pipeline output is and its hash, start-up
time, memory and per-request latency, and the scores. Entries are never rewritten or removed; a wrong
run is corrected by a later one that says so.

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
LOG = HERE / "experiments.json"
SCHEMA = 2
METRICS = ("ndcg@5", "ndcg@10", "precision@10", "recall@10")


def read(log: Path | None = None) -> list[dict]:
    log = log or LOG
    if not log.exists():
        return []
    entries: list[dict] = json.loads(log.read_text())
    return entries


def write(log: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    """Replace the log atomically (write a sibling file, then rename), so a crash never truncates it."""
    tmp = log.with_name(log.name + ".tmp")
    tmp.write_text(json.dumps(list(entries), indent=2, ensure_ascii=False) + "\n")
    tmp.replace(log)


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
    model: Mapping[str, Any] | None = None,
    effective: Mapping[str, Any] | None = None,
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
        "effective": dict(effective) if effective else None,  # what the commit served with (defaults + settings)
        "model": dict(model) if model else None,
        "env": {
            "python": platform.python_version(),
            **{p: _version(p) for p in ("numpy", "scikit-learn", "fastembed", "onnxruntime")},
        },
        "inputs": dict(inputs),
        "outputs": dict(outputs),
        "runtime": dict(runtime),
        "results": dict(results),
    }
    write(log, [*read(log), entry])
    return entry


def _rows(e: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """One table row per (experiment, fixture): dev retrieval scores, or dev dedup recall."""
    if e.get("schema", 1) == 1:
        o, i = e["results"]["overall"], e["inputs"]
        cfg = f"{i['method']['name']} v{i['method']['version']}"
        nums = tuple(f"{o[m]:.3f}" for m in METRICS) + ("", "", "", "")
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
    eff = e.get("effective") or {}
    cfg = e["settings"].get("EMBEDDING_MODEL") or eff.get("model") or "(commit default)"
    rows = []
    for fixture, by_split in e["results"].items():
        rt = e["runtime"].get(fixture, {})
        lat = rt.get("latency_ms", {})
        perf = (f"{rt.get('startup_s', '')}", f"{lat.get('mean', '')}", f"{lat.get('p95', '')}")
        dev = by_split.get("dev", {})
        if "overall" in dev:
            nums = tuple(f"{dev['overall'][m]:.3f}" for m in METRICS) + ("",)
        else:
            r = dev.get("recall_at_zero_false_duplicates")
            nums = ("", "", "", "", "" if r is None else f"{r:.3f}")
        rows.append(
            (str(e["experiment"]), e["date"][:10], e["commit"][:7], cfg, fixture, *nums, *perf, e["description"])
        )
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
        "start s",
        "mean ms",
        "p95 ms",
        "description",
    )
    rows = [head] + [r for e in entries for r in _rows(e)]
    widths = [max(len(r[c]) for r in rows) for c in range(len(head) - 1)]
    return "\n".join("  ".join(r[c].ljust(widths[c]) for c in range(len(widths))) + "  " + r[-1] for r in rows)


if __name__ == "__main__":
    print(table(read()))
    print("\nDev split. dedup R@0FP = duplicate recall at the strictest cut that flags no non-duplicate.")
    print("start s = service start-up incl. indexing; mean / p95 ms = GET /api/peers latency over HTTP.")
    sys.exit(0)
