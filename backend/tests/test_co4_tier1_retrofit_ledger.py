from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (
            (candidate / "docs" / "ops" / "tier1-retrofit-ledger.json").exists()
            and (candidate / "scripts" / "check-tier1-ledger.py").exists()
        ):
            return candidate
    raise AssertionError("Could not locate CivicRecords AI repository root.")


REPO_ROOT = find_repo_root()
LEDGER = REPO_ROOT / "docs" / "ops" / "tier1-retrofit-ledger.json"
CHECK = REPO_ROOT / "scripts" / "check-tier1-ledger.py"


def test_co4_tier1_ledger_static_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK), "--ledger", str(LEDGER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "PASS: 1 CivicSuite/civicrecords-ai CO-4 target release(s) are ledgered" in result.stdout


def test_co4_tier1_ledger_marks_v1410_as_pre_gate_only() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    entries = ledger["entries"]

    assert ledger["upstream_attested_baseline"]["tag"] == "v0.22.1"
    assert [entry["tag"] for entry in entries] == ["v1.4.10"]
    assert entries[0]["ledger_status"] == "pre_gate_no_attestation_do_not_promote"
    assert entries[0]["attestation_status"] == "none_pre_gate"
    assert "release-attestation.json" not in {
        asset["name"] for asset in entries[0]["release_assets"]
    }
