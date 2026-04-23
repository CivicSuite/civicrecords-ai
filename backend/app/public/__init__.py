"""T5D public-surface router package.

Only imported by :mod:`app.main` when ``settings.portal_mode == "public"``.
In ``PORTAL_MODE=private`` deployments this module is never loaded at
runtime, and every ``/public/*`` path returns 404.

Per Scott's 2026-04-22 Option A decision the public surface requires
authentication: residents self-register (creating :class:`UserRole.PUBLIC`
accounts) and sign in before submitting a records request. Anonymous
walk-up submission is NOT supported in this slice.
"""

from app.public.router import router as public_router

__all__ = ["public_router"]
