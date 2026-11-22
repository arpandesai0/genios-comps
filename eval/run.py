"""Run an eval: the pipeline at a given commit, on fixed inputs, scored against golden labels.

The pipeline is a black box. For each fixture this script:

1. checks out ``--commit`` into a temporary git worktree (so uncommitted changes can never leak in);
2. starts that commit's API (``uvicorn comps.api:app``) with ``DATA_DIR`` pointing at the fixture
   input from *this* checkout, plus the ``--set`` settings (e.g. ``EMBEDDING_MODEL``);
3. calls ``GET /api/peers`` for every query and saves the responses as served
   (``eval/runs/<NNN>/<fixture>.json``);
4. scores them with ``score.py`` against the fixture's golden labels and appends one row to the
   experiment log (``experiments.jsonl``).

The experiment number, not the commit, identifies a run: one commit can be run with several settings.

    .venv/bin/python eval/run.py --commit HEAD --set EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \\
        --desc "bge-small, description only"

Held-out splits are scored only with ``--held-out`` (once a configuration is final, docs/eval.md).
The code runs with this checkout's virtualenv; a commit that needs other dependencies can't be run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import experiments
from score import pair_score, score_dedup, score_retrieval

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = HERE / "runs"
FX = {"base": "USD", "rates": {"USD": 1.0}}
STARTUP_TIMEOUT_S = 900  # first start may download a model


@dataclass(frozen=True)
class Fixture:
    name: str
    path: Path
    kind: str  # "retrieval" or "dedup"
    k: int


FIXTURES = (
    Fixture("retrieval_v1", HERE / "fixtures" / "retrieval", "retrieval", 10),
    Fixture("independent", HERE / "fixtures" / "independent", "retrieval", 10),
    Fixture("dedup", HERE / "fixtures" / "dedup", "dedup", 50),
)

Get = Callable[[str, Mapping[str, Any]], Any]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


# --- inputs (golden side: built from the fixture files only) ---------------------------------------


def dedup_universe(pairs: Sequence[Mapping[str, Any]]) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    """A company universe holding both texts of every pair, and pair id -> (key a, key b).

    Every record gets distinct numbers, so the share-class merge (identical description and
    financials) never folds a duplicate pair into one company.
    """
    records, keys = [], {}
    for i, pair in enumerate(pairs):
        ab = []
        for side in ("a", "b"):
            n = 2 * i + (side == "b")
            ticker = f"D{i:03d}{side.upper()}"
            records.append(
                {
                    "id": f"dd{n:04d}",
                    "ticker": ticker,
                    "name": f"Pair {pair['id']} {side}",
                    "description": pair[side],
                    "sector": None,
                    "industry": None,
                    "sub_industry": None,
                    "country": "US",
                    "price_currency": "USD",
                    "reporting_currency": "USD",
                    "units": "millions",
                    "fiscal_year_end": "12-31",
                    "price": 10.0 + n,
                    "price_date": "2026-10-01",
                    "shares_outstanding": 50.0 + n,
                    "total_debt": 100.0,
                    "cash": 20.0,
                    "revenue": 400.0 + n,
                    "ebitda": 60.0,
                    "net_income": 20.0,
                }
            )
            ab.append(f"US:{ticker}")
        keys[pair["id"]] = (ab[0], ab[1])
    return records, keys


def golden_path(fixture: Fixture) -> Path:
    return fixture.path / ("labels.json" if fixture.kind == "retrieval" else "pairs.json")


def golden(fixture: Fixture) -> dict[str, Any]:
    """The golden spec: retrieval labels, or dedup pairs plus each pair's (key a, key b)."""
    spec = json.loads(golden_path(fixture).read_text())
    if fixture.kind == "dedup":
        spec["keys"] = dedup_universe(spec["pairs"])[1]
    return spec


def prepare(fixture: Fixture, workdir: Path) -> tuple[Path, list[str], dict[str, Any]]:
    """The data folder to serve, the queries to send, and the golden spec."""
    spec = golden(fixture)
    if fixture.kind == "retrieval":
        targets = sorted(t for split in spec["splits"].values() for t in split)
        return fixture.path, targets, spec
    data = workdir / f"{fixture.name}-data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "companies.json").write_text(json.dumps(dedup_universe(spec["pairs"])[0], indent=1) + "\n")
    (data / "fx_rates.json").write_text(json.dumps(FX) + "\n")
    return data, sorted({a for a, _ in spec["keys"].values()}), spec


def input_hash(data_dir: Path) -> str:
    return sha(b"".join((data_dir / n).read_bytes() for n in ("companies.json", "fx_rates.json")))


# --- running the pipeline (black box over HTTP) ----------------------------------------------------


def capture(get: Get, queries: Sequence[str], k: int) -> dict[str, Any]:
    """``GET /api/peers`` for every query, responses kept as served."""
    return {q: get("/api/peers", {"target": q, "k": k}) for q in queries}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def worktree(commit: str):
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    path = Path(tempfile.mkdtemp(prefix="comps-eval-"))
    subprocess.run(["git", "worktree", "add", "--detach", "-q", str(path), resolved], cwd=ROOT, check=True)
    try:
        yield resolved, path
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=ROOT, check=False)


@contextmanager
def serve(tree: Path, data_dir: Path, settings: Mapping[str, str]):
    """Start the commit's API on ``data_dir``; yield (get, startup seconds, server pid)."""
    port = _free_port()
    env = {**os.environ, **settings, "DATA_DIR": str(data_dir), "PYTHONPATH": str(tree / "src")}
    log = tempfile.TemporaryFile()  # noqa: SIM115 - closed in the finally block below
    cmd = [sys.executable, "-m", "uvicorn", "comps.api:app", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(cmd, cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"

    def get(path: str, params: Mapping[str, Any]) -> Any:
        with urllib.request.urlopen(f"{base}{path}?{urllib.parse.urlencode(params)}", timeout=120) as r:
            return json.load(r)

    start = time.monotonic()
    try:
        while True:
            if proc.poll() is not None:
                log.seek(0)
                raise RuntimeError(f"the service exited during start-up:\n{log.read().decode()[-3000:]}")
            try:
                urllib.request.urlopen(f"{base}/api/health", timeout=5).close()
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if time.monotonic() - start > STARTUP_TIMEOUT_S:
                    raise RuntimeError("the service did not start in time") from None
                time.sleep(0.5)
        yield get, round(time.monotonic() - start, 1), proc.pid
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        log.close()


def rss_mb(pid: int) -> float | None:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return round(int(out) / 1024, 1) if out.isdigit() else None


# --- scoring ---------------------------------------------------------------------------------------


def score(fixture: Fixture, captured: Mapping[str, Any], spec: Mapping[str, Any], splits: Sequence[str]) -> dict:
    out = {}
    if fixture.kind == "retrieval":
        records = json.loads((fixture.path / "companies.json").read_text())
        countries = {f"{r['country'] or '*'}:{r['ticker']}": r["country"] for r in records if r.get("ticker")}
        for split in splits:
            result = score_retrieval(captured, spec, countries, split)
            out[split] = {k: v for k, v in result.items() if k != "per_target"}
        return out
    for split in splits:
        rows = []
        for pair in spec["pairs"]:
            if pair["split"] != split:
                continue
            a, b = spec["keys"][pair["id"]]
            rows.append((pair_score(captured[a], b), bool(pair["duplicate"]), pair["kind"]))
        out[split] = score_dedup(rows)
    return out


# --- main ------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--commit", default="HEAD", help="commit to evaluate (default HEAD)")
    parser.add_argument("--desc", required=True, help="what this run tests")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="service setting")
    parser.add_argument("--fixture", action="append", choices=[f.name for f in FIXTURES], help="default: all")
    parser.add_argument("--held-out", action="store_true", help="also score the held-out splits")
    args = parser.parse_args(argv)
    if not args.desc.strip():
        parser.error("--desc needs a description of what the run tests")
    settings = dict(s.split("=", 1) for s in args.set)
    fixtures = [f for f in FIXTURES if args.fixture is None or f.name in args.fixture]
    splits = ["dev", "held_out"] if args.held_out else ["dev"]

    number = experiments.next_number()
    run_dir = RUNS / f"{number:03d}"
    results, inputs, outputs, runtime = {}, {}, {}, {}
    with worktree(args.commit) as (commit, tree), tempfile.TemporaryDirectory() as tmp:
        for fixture in fixtures:
            data_dir, queries, spec = prepare(fixture, Path(tmp))
            with serve(tree, data_dir, settings) as (get, startup_s, pid):
                captured = capture(get, queries, fixture.k)
                runtime[fixture.name] = {"startup_s": startup_s, "rss_mb": rss_mb(pid)}
            run_dir.mkdir(parents=True, exist_ok=True)
            out_path = run_dir / f"{fixture.name}.json"
            body = json.dumps({"commit": commit, "settings": settings, "k": fixture.k, "responses": captured})
            out_path.write_text(body + "\n")
            inputs[fixture.name] = {
                "input": input_hash(data_dir),
                "golden": sha(golden_path(fixture).read_bytes()),
                "queries": len(queries),
                "k": fixture.k,
            }
            outputs[fixture.name] = {"path": out_path.relative_to(ROOT).as_posix(), "sha": sha(out_path.read_bytes())}
            results[fixture.name] = score(fixture, captured, spec, splits)
            print(f"{fixture.name}: {json.dumps(results[fixture.name].get('dev'), indent=1)[:1500]}", file=sys.stderr)

    entry = experiments.record(
        number=number,
        description=args.desc,
        commit=commit,
        settings=settings,
        inputs=inputs,
        outputs=outputs,
        runtime=runtime,
        results=results,
    )
    print(f"logged experiment {entry['experiment']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
