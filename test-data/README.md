# Townlight Records synthetic test data

Everything under `redstone-valley-records-v1/` is independently authored,
explicitly fictional test data. It does not describe any real municipality,
person, case, address, account, or event.

Every artifact carries the watermark `TOWNLIGHT SYNTHETIC TEST DATA — NOT A
REAL MUNICIPAL RECORD`. The deterministic provenance and expected ground truth
are recorded in `redstone-valley-records-v1/manifest.json`.

Validate the fixture from the repository root with:

```text
python scripts/validate_synthetic_records.py
```

The validator checks the scenario inventory, provenance, license, watermarks,
relative references, byte size, SHA-256 hashes, duplicate relationship,
expected malformed input, reserved contact data, and common secret patterns.

The former top-level files were intentionally removed because they mixed a real
municipality's branding and contact details with invented people, incidents,
case identifiers, and operational claims. Git history is the only quarantine;
those unsafe files must not be copied into release artifacts or demo data.
