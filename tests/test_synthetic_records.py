from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test-data" / "redstone-valley-records-v1"
VALIDATOR_PATH = ROOT / "scripts" / "validate_synthetic_records.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_synthetic_records", VALIDATOR_PATH
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _copy_fixture(tmp_path: Path) -> Path:
    copy = tmp_path / "redstone-valley-records-v1"
    shutil.copytree(FIXTURE, copy)
    return copy


def _load_manifest(fixture: Path) -> dict:
    return json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(fixture: Path, manifest: dict) -> None:
    (fixture / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _refresh_artifact_digest(fixture: Path, path_name: str) -> None:
    manifest = _load_manifest(fixture)
    data = (fixture / path_name).read_bytes()
    case = next(item for item in manifest["cases"] if item["path"] == path_name)
    case["byte_size"] = len(data)
    case["sha256"] = hashlib.sha256(data).hexdigest()
    _write_manifest(fixture, manifest)


def test_committed_fixture_passes_deterministic_validation() -> None:
    assert VALIDATOR.validate_fixture(FIXTURE) == []


def test_hash_drift_is_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    artifact = fixture / "ordinary-council-packet.txt"
    artifact.write_text(
        artifact.read_text(encoding="utf-8") + "drift\n", encoding="utf-8"
    )

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("sha256 does not match" in finding for finding in findings)


def test_ground_truth_drift_is_rejected_by_pinned_contract(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    manifest = _load_manifest(fixture)
    recovery = next(
        item for item in manifest["cases"] if item["scenario"] == "recovery"
    )
    recovery["ground_truth"]["expected_resume_stage"] = "skip-human-review"
    _write_manifest(fixture, manifest)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("does not match the pinned" in finding for finding in findings)


def test_broken_reference_is_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    manifest = _load_manifest(fixture)
    duplicate = next(
        item for item in manifest["cases"] if item["scenario"] == "duplicate"
    )
    duplicate["ground_truth"]["duplicates_case_id"] = "missing-case"
    _write_manifest(fixture, manifest)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("duplicates_case_id is broken" in finding for finding in findings)


def test_unlicensed_provenance_is_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    manifest = _load_manifest(fixture)
    manifest["cases"][0]["provenance"]["license"] = "unknown"
    _write_manifest(fixture, manifest)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("provenance license must be CC0-1.0" in finding for finding in findings)


def test_missing_watermark_is_rejected_even_with_updated_digest(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    path_name = "ordinary-council-packet.txt"
    artifact = fixture / path_name
    text = artifact.read_text(encoding="utf-8").replace(VALIDATOR.WATERMARK, "UNMARKED")
    artifact.write_text(text, encoding="utf-8", newline="\n")
    _refresh_artifact_digest(fixture, path_name)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("synthetic watermark is missing" in finding for finding in findings)


def test_non_reserved_contact_data_is_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    path_name = "vendor-followup.eml"
    artifact = fixture / path_name
    text = artifact.read_text(encoding="utf-8").replace(
        "example.invalid", "example.com"
    )
    artifact.write_text(text, encoding="utf-8", newline="\n")
    _refresh_artifact_digest(fixture, path_name)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("email domain is not reserved" in finding for finding in findings)


def test_secret_like_value_is_rejected_even_with_updated_digest(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    path_name = "ordinary-council-packet.txt"
    artifact = fixture / path_name
    synthetic_secret_shape = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz123456"
    artifact.write_text(
        artifact.read_text(encoding="utf-8") + synthetic_secret_shape + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _refresh_artifact_digest(fixture, path_name)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("contains a secret-like value" in finding for finding in findings)


def test_non_reproducible_timestamp_is_rejected(tmp_path: Path) -> None:
    fixture = _copy_fixture(tmp_path)
    manifest = _load_manifest(fixture)
    manifest["generated_at"] = "now"
    _write_manifest(fixture, manifest)

    findings = VALIDATOR.validate_fixture(fixture)

    assert any("generated_at must remain fixed" in finding for finding in findings)
