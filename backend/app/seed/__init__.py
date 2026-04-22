"""First-boot seed orchestration (Tier 5 Blocker B).

See ``app.seed.first_boot.run_first_boot_seeds`` — called from
``app.main`` lifespan after the first admin user has been created.
"""

from app.seed.first_boot import run_first_boot_seeds

__all__ = ["run_first_boot_seeds"]
