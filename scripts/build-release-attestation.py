from __future__ import annotations

import argparse
from pathlib import Path

from civiccore.release_provenance import build_release_attestation, canonical_json_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--tag-ref-type", required=True, choices=["commit", "tag"])
    parser.add_argument("--tag-ref-sha", required=True)
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--target-tree", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("release-attestation.json"))
    args = parser.parse_args()

    attestation = build_release_attestation(
        repo=args.repo,
        tag_name=args.tag,
        tag_ref_type=args.tag_ref_type,
        tag_ref_sha=args.tag_ref_sha,
        target_commit=args.target_commit,
        target_tree=args.target_tree,
        workflow_run_id=args.workflow_run_id,
        artifacts_dir=args.artifacts_dir,
    )
    args.output.write_bytes(canonical_json_bytes(attestation))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
