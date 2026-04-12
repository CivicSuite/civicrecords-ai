import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connectors import SystemCatalog

CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "systems_catalog.json"


async def load_catalog(session: AsyncSession) -> int:
    """Load or refresh the systems catalog from the bundled JSON file.
    Returns count of entries loaded. Returns 0 gracefully if file not found."""
    if not CATALOG_PATH.exists():
        print(f"Warning: Systems catalog not found at {CATALOG_PATH}, skipping load")
        return 0

    with open(CATALOG_PATH) as f:
        data = json.load(f)

    catalog_version = data["catalog_version"]

    # Check if already loaded at this version
    existing = await session.execute(
        select(SystemCatalog)
        .where(SystemCatalog.catalog_version == catalog_version)
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return 0  # Already loaded

    count = 0
    for domain_entry in data["domains"]:
        domain = domain_entry["domain"]
        for system in domain_entry["systems"]:
            entry = SystemCatalog(
                domain=domain,
                function=domain,
                vendor_name=system["vendor_name"],
                access_protocol=system["access_protocol"],
                data_shape=system["data_shape"],
                common_record_types=system["common_record_types"],
                redaction_tier=system["redaction_tier"],
                discovery_hints=system.get("discovery_hints", {}),
                catalog_version=catalog_version,
            )
            session.add(entry)
            count += 1

    await session.commit()
    return count
