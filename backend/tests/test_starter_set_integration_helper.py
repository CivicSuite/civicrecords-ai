from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(os.environ.get("CIVICRECORDS_REPO_ROOT", Path(__file__).resolve().parents[2]))


def _write_umbrella_fixture(root: Path) -> None:
    installer = root / "installer"
    dist = installer / "dist"
    docs = root / "docs" / "installer"
    dist.mkdir(parents=True)
    docs.mkdir(parents=True)
    (installer / "modules.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "id": "clerk-core",
                        "modules": ["civiccore", "civicrecords-ai", "civicclerk"],
                    }
                ],
                "modules": [
                    {"id": "civiccore", "current_version": "1.2.0", "selectable": False},
                    {
                        "id": "civicrecords-ai",
                        "current_version": "1.7.3",
                        "selectable": True,
                        "civiccore_requirement": "1.2.0",
                        "dependencies": ["civiccore"],
                    },
                    {
                        "id": "civicclerk",
                        "current_version": "1.0.1",
                        "selectable": True,
                        "dependencies": ["civiccore"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (docs / "starter-set-release-contract.md").write_text(
        "\n".join(
            [
                "CivicSunshine reports v1.7.3",
                "CivicClerk reports v1.0.1 with CivicCore v1.2.0",
                "--staff-mode bearer --workflow-proof",
                "Package Cleanroom Contract",
                "workflow_proof_requested=true",
                "not yet a claim that CivicSunshine and CivicClerk exchange workflow records",
            ]
        ),
        encoding="utf-8",
    )
    (dist / "CivicSuite-clerk-core-linux-0.1.0.tar.gz").write_text("linux\n", encoding="utf-8")
    (dist / "CivicSuite-clerk-core-windows-0.1.0.zip").write_text("windows\n", encoding="utf-8")


def test_starter_set_integration_passes_with_umbrella_contract(tmp_path: Path) -> None:
    _write_umbrella_fixture(tmp_path)
    report = tmp_path / "starter-set.json"

    result = subprocess.run(
        [
            "python",
            "scripts/check_starter_set_integration.py",
            "--umbrella-root",
            str(tmp_path),
            "--require-archives",
            "--output",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "starter_set_ready=true" in result.stdout
    assert "release_evidence_ready=true" in result.stdout
    assert "[PASS] clerk-core profile order" in result.stdout
    assert "[PASS] CivicSunshine module contract" in result.stdout
    assert "[PASS] CivicClerk pairing" in result.stdout
    assert "[PASS] starter-set release contract" in result.stdout
    assert "[PASS] starter-set archives" in result.stdout
    assert "STARTER-SET-INTEGRATION: RELEASE-EVIDENCE-READY" in result.stdout
    assert '"release_evidence_ready": true' in report.read_text(encoding="utf-8")


def test_starter_set_integration_print_only_documents_contract() -> None:
    result = subprocess.run(
        ["python", "scripts/check_starter_set_integration.py", "--print-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Umbrella clerk-core profile installs CivicCore" in result.stdout
    assert "package workflow proof" in result.stdout
    assert "STARTER-SET-INTEGRATION: PLAN" in result.stdout


def test_starter_set_integration_fails_when_manifest_is_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "python",
            "scripts/check_starter_set_integration.py",
            "--umbrella-root",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "[FAIL] umbrella checkout" in result.stdout
    assert "STARTER-SET-INTEGRATION: FAILED" in result.stdout
