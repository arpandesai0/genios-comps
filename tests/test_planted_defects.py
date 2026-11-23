"""End-to-end acceptance test: a messy synthetic dataset with planted defects.

``tests/fixtures/planted_defects/`` holds a small universe in which each company carries one known
problem, and ``expected.json`` holds the expected result, derived by hand from the documented rules.
The whole pipeline runs from the files (load, validate, resolve, cross-company checks, finance) and
the test requires an exact match: every planted defect is caught, and nothing else is reported.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from comps.config import IngestConfig, Settings
from comps.models import Finding, MetricValue
from comps.retrieval import TfidfRetriever
from comps.service import Snapshot, build_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "planted_defects"
DOCS = Path(__file__).parent.parent / "docs"
EXPECTED = json.loads((FIXTURE / "expected.json").read_text())


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return build_snapshot(Settings(data_dir=FIXTURE, ingest=IngestConfig()), TfidfRetriever())


def _key(f: Finding) -> tuple:
    return (f.code, f.severity, f.fields, f.record_ids, f.entity_keys)


def _expected_key(spec: dict, company: str | None) -> tuple:
    default_keys = [company] if company else []
    return (
        spec["code"],
        spec["severity"],
        tuple(spec["fields"]),
        tuple(spec["record_ids"]),
        tuple(spec.get("entity_keys", default_keys)),
    )


def _metric(v: MetricValue) -> str | list[str]:
    if v.status == "missing":
        return list(v.missing_inputs)
    assert v.display is not None
    return v.display


def test_record_count_reference_date_and_companies(snapshot):
    assert snapshot.dataset.record_count == EXPECTED["record_count"]
    assert snapshot.dataset.reference_date == date.fromisoformat(EXPECTED["reference_date"])
    assert sorted(snapshot.companies) == sorted(EXPECTED["companies"])


def test_dataset_level_findings(snapshot):
    expected = [_expected_key(s, None) for s in EXPECTED["dataset_findings"]]
    assert Counter(_key(f) for f in snapshot.dataset.findings) == Counter(expected)


@pytest.mark.parametrize("key", sorted(EXPECTED["companies"]))
def test_company(snapshot, key):
    spec = EXPECTED["companies"][key]
    view = snapshot.companies[key]

    assert [o.record_id for o in view.entity.observations] == spec["observations"], spec["plant"]
    assert [o.record_id for o in view.entity.superseded] == spec.get("superseded", []), spec["plant"]

    expected_findings = Counter(_expected_key(s, key) for s in spec["findings"])
    assert Counter(_key(f) for f in view.findings) == expected_findings, spec["plant"]

    metrics = EXPECTED["baseline_metrics"] if spec["metrics"] == "baseline" else spec["metrics"]
    actual = {name: _metric(v) for name, v in vars(view.metrics).items()}
    assert actual == metrics, spec["plant"]


def test_no_finding_outside_the_manifest(snapshot):
    """Every finding anywhere in the snapshot is accounted for, including on superseded records."""
    expected = Counter(_expected_key(s, None) for s in EXPECTED["dataset_findings"])
    for key, spec in EXPECTED["companies"].items():
        expected.update(_expected_key(s, key) for s in spec["findings"])
    assert Counter(_key(f) for f in snapshot.findings) == expected


def _documented_codes() -> set[str]:
    """Finding codes in the ingestion catalogue table plus the finance codes it points to."""
    text = (DOCS / "ingestion.md").read_text()
    catalogue = text.split("## Findings catalogue", 1)[1].split("\n## ", 1)[0]
    codes = set(re.findall(r"^\| `([a-z_]+)` \|", catalogue, flags=re.MULTILINE))
    finance = re.search(r"Finance adds `([a-z_]+)` and `([a-z_]+)`", catalogue)
    assert finance, "docs/ingestion.md no longer names the finance codes as 'Finance adds `a` and `b`'"
    return codes | set(finance.groups())


def _emitted_codes() -> set[str]:
    """Finding codes the source can raise: ``code="..."`` arguments and ``f.add("...", ...)`` calls."""
    src = "\n".join(p.read_text() for p in sorted((Path(__file__).parent.parent / "src" / "comps").glob("*.py")))
    return set(re.findall(r'\bcode="([a-z_]+)"', src)) | set(re.findall(r'\bf\.add\(\s*"([a-z_]+)"', src))


def test_catalogue_source_and_fixture_agree_on_finding_codes():
    planted = {s["code"] for s in EXPECTED["dataset_findings"]}
    for spec in EXPECTED["companies"].values():
        planted |= {s["code"] for s in spec["findings"]}
    documented = _documented_codes()
    emitted = _emitted_codes()
    assert emitted - documented == set(), "codes the source can raise that the catalogue does not document"
    assert documented - emitted == set(), "documented codes the source never raises"
    assert documented - planted == set(), "documented finding codes with no planted defect"
    assert planted - documented == set(), "planted finding codes missing from the catalogue"
