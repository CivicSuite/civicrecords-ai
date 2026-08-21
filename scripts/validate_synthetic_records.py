#!/usr/bin/env python3
"""Validate the deterministic Redstone Valley records fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = ROOT / "test-data" / "redstone-valley-records-v1"
WATERMARK = "TOWNLIGHT SYNTHETIC TEST DATA — NOT A REAL MUNICIPAL RECORD"
FIXED_GENERATED_AT = "2042-01-01T00:00:00Z"
PINNED_MANIFEST_SHA256 = (
    "ff01caffb0a3ece523f3d3011fec90899bc896a18bca585c85f31fc21bfda8cd"
)
EXPECTED_SCENARIOS = {
    "ordinary",
    "scanned",
    "tabular",
    "email",
    "malformed",
    "prompt_injection",
    "pii",
    "ambiguous_exemption",
    "duplicate",
    "notification_failure",
    "recovery",
}
UNSAFE_REPLACED_PATHS = {
    "city-council-minutes-feb2025.txt",
    "police-incident-summary-jan2025.txt",
    "water-quality-report-2025.txt",
}
BANNED_REAL_WORLD_MARKERS = (
    "city of longmont",
    "longmont police department",
    "longmontcolorado.gov",
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE
)
PHONE_PATTERN = re.compile(r"(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"(?im)^\s*(?:AZURE_CLIENT_SECRET|JWT_SECRET|ENCRYPTION_KEY)\s*[:=]\s*\S+"
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_manifest(path: Path, findings: list[str]) -> dict[str, Any] | None:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        findings.append("manifest.json is missing")
        return None
    if _sha256(data) != PINNED_MANIFEST_SHA256:
        findings.append(
            "manifest.json does not match the pinned Redstone Valley v1 contract"
        )
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(f"manifest.json is not valid UTF-8 JSON: {exc}")
        return None
    if not isinstance(value, dict):
        findings.append("manifest.json must contain a JSON object")
        return None
    return value


def _safe_relative_path(fixture_dir: Path, raw_path: object) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.name != raw_path:
        return None
    resolved = (fixture_dir / candidate).resolve()
    if resolved.parent != fixture_dir.resolve():
        return None
    return resolved


def validate_fixture(fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> list[str]:
    """Return deterministic validation findings; an empty list means valid."""

    fixture_dir = fixture_dir.resolve()
    findings: list[str] = []
    manifest = _load_manifest(fixture_dir / "manifest.json", findings)
    if manifest is None:
        return findings

    if manifest.get("schema_version") != 1:
        findings.append("schema_version must be 1")
    if manifest.get("fixture_id") != "townlight.redstone-valley.records.v1":
        findings.append("fixture_id is not the canonical Redstone Valley v1 identifier")
    if manifest.get("fixture_version") != "1.0.0":
        findings.append("fixture_version must remain 1.0.0")
    if manifest.get("generated_at") != FIXED_GENERATED_AT:
        findings.append(f"generated_at must remain fixed at {FIXED_GENERATED_AT}")
    if manifest.get("watermark") != WATERMARK:
        findings.append("manifest watermark is missing or changed")
    if manifest.get("license") != "CC0-1.0":
        findings.append("fixture license must be CC0-1.0")

    municipality = manifest.get("municipality")
    if not isinstance(municipality, dict) or municipality.get("fictional") is not True:
        findings.append("municipality must be explicitly fictional")
    elif municipality.get("real_world_basis") != "none":
        findings.append("municipality real_world_basis must be 'none'")

    authorship = manifest.get("authorship")
    if not isinstance(authorship, dict):
        findings.append("authorship must be an object")
    else:
        if authorship.get("external_sources") != []:
            findings.append("external_sources must be an empty list")
        if authorship.get("contains_scraped_material") is not False:
            findings.append("contains_scraped_material must be false")
        if authorship.get("contains_real_personal_data") is not False:
            findings.append("contains_real_personal_data must be false")

    reproducibility = manifest.get("reproducibility")
    expected_reproducibility = {
        "encoding": "UTF-8",
        "line_endings": "LF",
        "digest_algorithm": "SHA-256",
        "timestamps_are_fixed": True,
        "network_required": False,
    }
    if reproducibility != expected_reproducibility:
        findings.append("reproducibility contract is missing or non-deterministic")

    required = manifest.get("required_scenarios")
    if not isinstance(required, list) or set(required) != EXPECTED_SCENARIOS:
        findings.append("required_scenarios must list the complete R1-C scenario set")
    elif len(required) != len(set(required)):
        findings.append("required_scenarios contains duplicates")

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        findings.append("cases must be a list")
        return findings

    ids: set[str] = set()
    scenarios: set[str] = set()
    paths: set[str] = set()
    cases_by_id: dict[str, dict[str, Any]] = {}
    artifact_bytes: dict[str, bytes] = {}

    for index, raw_case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(raw_case, dict):
            findings.append(f"{label} must be an object")
            continue
        case = raw_case
        case_id = case.get("id")
        scenario = case.get("scenario")
        raw_path = case.get("path")
        if not isinstance(case_id, str) or not case_id:
            findings.append(f"{label}.id is missing")
        elif case_id in ids:
            findings.append(f"duplicate case id: {case_id}")
        else:
            ids.add(case_id)
            cases_by_id[case_id] = case
        if not isinstance(scenario, str):
            findings.append(f"{label}.scenario is missing")
        else:
            scenarios.add(scenario)
        path = _safe_relative_path(fixture_dir, raw_path)
        if path is None:
            findings.append(f"{label}.path must be one safe relative filename")
            continue
        path_name = path.name
        if path_name in paths:
            findings.append(f"duplicate artifact path: {path_name}")
        paths.add(path_name)
        if not path.is_file():
            findings.append(f"referenced artifact is missing: {path_name}")
            continue

        data = path.read_bytes()
        artifact_bytes[path_name] = data
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"{path_name}: artifact is not UTF-8")
            continue
        if b"\r\n" in data or b"\r" in data:
            findings.append(f"{path_name}: artifact must use LF line endings")
        if WATERMARK not in text:
            findings.append(f"{path_name}: synthetic watermark is missing")
        if case.get("byte_size") != len(data):
            findings.append(f"{path_name}: byte_size does not match artifact bytes")
        if case.get("sha256") != _sha256(data):
            findings.append(f"{path_name}: sha256 does not match artifact bytes")

        provenance = case.get("provenance")
        expected_source_path = f"synthetic://redstone-valley/records/v1/{path_name}"
        if not isinstance(provenance, dict):
            findings.append(f"{path_name}: provenance must be an object")
        else:
            if provenance.get("source_path") != expected_source_path:
                findings.append(f"{path_name}: source_path is missing or non-canonical")
            if provenance.get("connector_type") != "fixture":
                findings.append(f"{path_name}: connector_type must be fixture")
            if provenance.get("connector_id") != "townlight-redstone-valley-v1":
                findings.append(f"{path_name}: connector_id is missing or changed")
            if provenance.get("authorship") != "independent":
                findings.append(
                    f"{path_name}: provenance authorship must be independent"
                )
            if provenance.get("license") != "CC0-1.0":
                findings.append(f"{path_name}: provenance license must be CC0-1.0")

        ground_truth = case.get("ground_truth")
        if not isinstance(ground_truth, dict):
            findings.append(f"{path_name}: ground_truth must be an object")
        elif not isinstance(ground_truth.get("human_review_required"), bool):
            findings.append(
                f"{path_name}: ground_truth must state human_review_required"
            )

        lower_text = text.lower()
        for marker in BANNED_REAL_WORLD_MARKERS:
            if marker in lower_text:
                findings.append(
                    f"{path_name}: contains banned real-world marker {marker!r}"
                )
        for domain in EMAIL_PATTERN.findall(text):
            if not domain.lower().endswith(".invalid"):
                findings.append(f"{path_name}: email domain is not reserved: {domain}")
        for phone in PHONE_PATTERN.findall(text):
            digits = re.sub(r"\D", "", phone)
            if not (len(digits) == 11 and digits.startswith("120255501")):
                findings.append(
                    f"{path_name}: telephone is not in the reserved 202-555-01xx block"
                )
        for ssn in SSN_PATTERN.findall(text):
            if ssn != "000-00-0000":
                findings.append(
                    f"{path_name}: SSN-shaped value is not the reserved placeholder"
                )
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{path_name}: contains a secret-like value")

        if scenario == "malformed":
            try:
                json.loads(text)
            except json.JSONDecodeError:
                pass
            else:
                findings.append(
                    f"{path_name}: malformed scenario unexpectedly parses as JSON"
                )
        elif path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                findings.append(f"{path_name}: expected valid JSON: {exc}")

        if scenario == "pii" and isinstance(ground_truth, dict):
            spans = ground_truth.get("expected_sensitive_spans")
            if not isinstance(spans, list) or not spans:
                findings.append(
                    f"{path_name}: PII ground truth has no expected_sensitive_spans"
                )
            else:
                for span in spans:
                    value = span.get("value") if isinstance(span, dict) else None
                    if not isinstance(value, str) or value not in text:
                        findings.append(
                            f"{path_name}: sensitive span is missing from artifact: {value!r}"
                        )

    if scenarios != EXPECTED_SCENARIOS:
        missing = sorted(EXPECTED_SCENARIOS - scenarios)
        extra = sorted(scenarios - EXPECTED_SCENARIOS)
        findings.append(
            f"scenario inventory mismatch; missing={missing}, extra={extra}"
        )

    actual_files = {p.name for p in fixture_dir.iterdir() if p.is_file()} - {
        "manifest.json"
    }
    if actual_files != paths:
        findings.append(
            f"artifact inventory mismatch; unlisted={sorted(actual_files - paths)}, "
            f"missing={sorted(paths - actual_files)}"
        )

    for case in cases_by_id.values():
        if case.get("scenario") != "duplicate":
            continue
        ground_truth = case.get("ground_truth", {})
        duplicate_of = ground_truth.get("duplicates_case_id")
        target = cases_by_id.get(duplicate_of)
        if target is None:
            findings.append(
                f"{case.get('id')}: duplicates_case_id is broken: {duplicate_of!r}"
            )
            continue
        if case.get("sha256") != target.get("sha256"):
            findings.append(
                f"{case.get('id')}: duplicate hash differs from {duplicate_of}"
            )
        left = artifact_bytes.get(str(case.get("path")))
        right = artifact_bytes.get(str(target.get("path")))
        if left is not None and right is not None and left != right:
            findings.append(
                f"{case.get('id')}: duplicate bytes differ from {duplicate_of}"
            )

    fixture_parent = fixture_dir.parent
    if fixture_parent.name == "test-data":
        for unsafe_name in sorted(UNSAFE_REPLACED_PATHS):
            if (fixture_parent / unsafe_name).exists():
                findings.append(f"unsafe replaced fixture still exists: {unsafe_name}")

    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=DEFAULT_FIXTURE_DIR,
        help="Fixture directory to validate (defaults to the committed Redstone Valley v1 fixture).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = validate_fixture(args.fixture_dir)
    if findings:
        print("SYNTHETIC-RECORDS: FAILED")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print(
        f"SYNTHETIC-RECORDS: PASSED ({len(EXPECTED_SCENARIOS)} deterministic scenarios)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
