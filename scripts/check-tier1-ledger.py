from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPECTED_REPO = "CivicSuite/civicrecords-ai"
EXPECTED_TAGS = {"v1.4.10"}
ATTESTATION_ASSETS = {"release-attestation.json", "release-attestation.json.bundle"}


class LedgerError(Exception):
    pass


def load_ledger(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    if not isinstance(ledger, dict):
        raise LedgerError("ledger root must be a JSON object")
    return ledger


def validate_ledger(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    if ledger.get("schema_version") != 1:
        raise LedgerError("schema_version must be 1")
    if ledger.get("repo") != EXPECTED_REPO:
        raise LedgerError(f"repo must be {EXPECTED_REPO}")
    if ledger.get("upstream_attested_baseline", {}).get("tag") != "v0.22.1":
        raise LedgerError("upstream_attested_baseline.tag must be v0.22.1")

    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise LedgerError("entries must be a list")
    tags = {str(entry.get("tag", "")) for entry in entries}
    if tags != EXPECTED_TAGS:
        raise LedgerError(f"ledger tags {sorted(tags)} do not match {sorted(EXPECTED_TAGS)}")
    if ledger.get("target_release_count") != len(entries):
        raise LedgerError("target_release_count does not match entries length")

    for entry in entries:
        assets = {asset["name"] for asset in entry.get("release_assets", [])}
        if entry.get("ledger_status") != "pre_gate_no_attestation_do_not_promote":
            raise LedgerError(f"{entry.get('tag')} must be pre-gate/no-attestation")
        if entry.get("attestation_status") != "none_pre_gate":
            raise LedgerError(f"{entry.get('tag')} attestation_status must be none_pre_gate")
        if ATTESTATION_ASSETS & assets:
            raise LedgerError(f"{entry.get('tag')} lists attestation assets despite pre-gate status")
    return entries


def live_asset_names(repo: str, tag: str) -> set[str]:
    result = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo, "--json", "assets"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return {asset["name"] for asset in payload.get("assets", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("docs/ops/tier1-retrofit-ledger.json"),
    )
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    try:
        ledger = load_ledger(args.ledger)
        entries = validate_ledger(ledger)
        if args.live:
            for entry in entries:
                expected = {asset["name"] for asset in entry["release_assets"]}
                actual = live_asset_names(ledger["repo"], entry["tag"])
                if actual != expected:
                    raise LedgerError(
                        f"{entry['tag']} live assets {sorted(actual)} do not match "
                        f"ledger assets {sorted(expected)}"
                    )
        print(f"PASS: {len(entries)} {ledger['repo']} CO-4 target release(s) are ledgered")
    except LedgerError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
