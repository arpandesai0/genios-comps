"""Loading files, FX validation and blocking errors."""

import hashlib
import json

import pytest

from comps.ingest import DatasetError, build_dataset, load_dataset
from conftest import make_record


def write(tmp_path, companies, fx):
    (tmp_path / "companies.json").write_text(json.dumps(companies))
    (tmp_path / "fx_rates.json").write_text(json.dumps(fx))
    return tmp_path


def test_load_dataset_from_folder_records_file_hashes(tmp_path, fx):
    d = write(tmp_path, [make_record()], fx)
    ds = load_dataset(d)
    assert [f.name for f in ds.files] == ["companies.json", "fx_rates.json"]
    assert ds.files[0].sha256 == hashlib.sha256((d / "companies.json").read_bytes()).hexdigest()
    assert ds.record_count == 1 and list(ds.entities) == ["US:ACME"]


def test_different_files_give_different_versions(tmp_path, fx):
    v1 = load_dataset(write(tmp_path, [make_record()], fx)).version
    v2 = load_dataset(write(tmp_path, [make_record(price=21.0)], fx)).version
    assert v1 != v2


@pytest.mark.parametrize("content", ["{not json", ""])
def test_invalid_json_is_blocking(tmp_path, fx, content):
    write(tmp_path, [], fx)
    (tmp_path / "companies.json").write_text(content)
    with pytest.raises(DatasetError, match="not valid JSON"):
        load_dataset(tmp_path)


def test_missing_file_is_blocking(tmp_path):
    with pytest.raises(DatasetError, match="cannot read"):
        load_dataset(tmp_path)


def test_companies_must_be_a_list(fx):
    with pytest.raises(DatasetError, match="JSON list"):
        build_dataset({"companies": []}, fx)


def test_no_usable_records_is_blocking(fx):
    with pytest.raises(DatasetError, match="no usable"):
        build_dataset([], fx)
    with pytest.raises(DatasetError, match="no usable"):
        build_dataset(["oops", 3], fx)


def test_non_object_records_are_skipped_with_an_error_finding(fx):
    ds = build_dataset([make_record(), "oops"], fx)
    assert list(ds.entities) == ["US:ACME"]
    (f,) = ds.findings
    assert f.code == "invalid_record" and f.severity == "error"


@pytest.mark.parametrize(
    "fx_doc",
    [
        [],
        {"base": "USD"},
        {"base": "EUR", "rates": {"USD": 0.9}},
        {"base": "USD", "rates": {"USD": 1.1}},
    ],
)
def test_malformed_fx_is_blocking(fx_doc):
    with pytest.raises(DatasetError):
        build_dataset([make_record()], fx_doc)


def test_usd_is_implicit_and_bad_rates_are_dropped_with_a_finding():
    ds = build_dataset([make_record(reporting_currency="EUR")], {"base": "usd", "rates": {"EUR": -1, "gbp": 1.3}})
    assert ds.fx_rates == {"USD": 1.0, "GBP": 1.3}
    assert [f.code for f in ds.findings] == ["invalid_fx_rate"]
    o = ds.entities["US:ACME"].latest
    assert o.usd.revenue is None
    assert [f.code for f in o.findings] == ["unknown_currency"]
