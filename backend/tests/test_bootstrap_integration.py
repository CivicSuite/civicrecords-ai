"""Integration tests for the T2C fresh-start bootstrap failure path.

This file does what the T2C remediation plan literally asked for: prove that
a fresh process loading app.config with the `.env.example` placeholder for
``FIRST_ADMIN_PASSWORD`` exits non-zero and surfaces the validator's error.
That is the same import-time path that runs when ``docker compose up`` boots
the api container — when ``Settings()`` raises at module load, uvicorn never
starts, and the container exits.

Distinct from ``test_config_validation.py``: that file constructs ``Settings``
inline in the test process (unit-level proof that the validator works).
This file launches a fresh Python subprocess with the placeholder env, which
mirrors the container bootstrap end-to-end:

  * env-loading mechanism: same (pydantic-settings reads from ``os.environ``)
  * module import order: same (``Settings()`` instantiated at import time)
  * failure mode: same (validator raises, process exits non-zero)

A complementary CI job (``bootstrap-failure`` in ``.github/workflows/ci.yml``)
runs the same check through ``docker compose run`` against the real api
image so the literal ``docker compose`` path is also exercised on every PR.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys


# Env vars that must be carried into the subprocess so it can find Python
# and behave consistently across platforms.
_ENV_PASSTHROUGH = frozenset({
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONIOENCODING",
    "SYSTEMROOT",
    "TZ",
    "LANG",
    "LC_ALL",
})

# Project root that contains the `app` package. When the subprocess runs from
# tmp_path (so .env in the parent's cwd can't interfere), Python's default
# sys.path is just cwd; without an explicit PYTHONPATH the subprocess can't
# `from app.config import ...`. This file lives at backend/tests/, so the
# parent of its directory is the import root (`/app` in the docker container,
# `<repo>/backend` locally).
_PROJECT_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)

_VALID_JWT = "a" * 64
_VALID_PASSWORD = "S3cure!FreshAdminPwd-2026"
_PLACEHOLDER_PASSWORD = "CHANGE-ME-on-first-login"  # exact .env.example value
_BOOTSTRAP_SNIPPET = "from app.config import Settings; Settings()"


def _minimal_env(**overrides: str) -> dict[str, str]:
    """Build a minimal env for the bootstrap subprocess.

    Carries only the platform basics needed to launch Python; deliberately
    omits the test process's TESTING flag and its own valid password so the
    subprocess sees a fresh environment with only the overrides we set.
    Forces PYTHONPATH to include the project root so `from app.config import
    Settings` resolves even when cwd is a tmp dir.
    """
    env = {k: v for k, v in os.environ.items() if k in _ENV_PASSTHROUGH}
    # Prepend project root to any inherited PYTHONPATH so the subprocess can
    # import the `app` package regardless of cwd.
    inherited_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        _PROJECT_ROOT + os.pathsep + inherited_pp if inherited_pp else _PROJECT_ROOT
    )
    env.update(overrides)
    return env


def _run_bootstrap(env: dict[str, str], cwd: str) -> subprocess.CompletedProcess:
    """Spawn a fresh Python that does what container startup does."""
    return subprocess.run(
        [sys.executable, "-c", _BOOTSTRAP_SNIPPET],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )


def test_fresh_bootstrap_fails_with_env_example_placeholder(tmp_path):
    """A fresh process with the .env.example placeholder must exit non-zero
    and surface the FIRST_ADMIN_PASSWORD error.

    This is the literal failure mode the T2C plan requires:
    ``docker compose up`` would hit the same Settings() construction at
    api-container import time and die for the same reason.
    """
    env = _minimal_env(
        JWT_SECRET=_VALID_JWT,
        FIRST_ADMIN_PASSWORD=_PLACEHOLDER_PASSWORD,
    )
    result = _run_bootstrap(env, cwd=str(tmp_path))

    assert result.returncode != 0, (
        f"Bootstrap should have failed but exited 0. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + result.stderr
    assert "FIRST_ADMIN_PASSWORD" in combined, (
        f"Expected FIRST_ADMIN_PASSWORD in error output. Got: {combined!r}"
    )


def test_fresh_bootstrap_passes_with_strong_password(tmp_path):
    """Control: a fresh process with a valid strong password must exit 0.

    Without this, a broken Python install or import path would make the
    failure test pass for the wrong reason — this proves the subprocess
    machinery itself works.
    """
    env = _minimal_env(
        JWT_SECRET=_VALID_JWT,
        FIRST_ADMIN_PASSWORD=_VALID_PASSWORD,
    )
    result = _run_bootstrap(env, cwd=str(tmp_path))

    assert result.returncode == 0, (
        f"Bootstrap should have succeeded but exited {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_fresh_bootstrap_fails_with_short_password(tmp_path):
    """The length-check branch fires in the same fresh-subprocess path."""
    env = _minimal_env(
        JWT_SECRET=_VALID_JWT,
        FIRST_ADMIN_PASSWORD="short",
    )
    result = _run_bootstrap(env, cwd=str(tmp_path))

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "FIRST_ADMIN_PASSWORD" in combined
    # The error message includes the minimum length number
    assert "12" in combined or "characters" in combined


def test_fresh_bootstrap_fails_with_blocklist_password(tmp_path):
    """A common blocklist value also fails the bootstrap path."""
    env = _minimal_env(
        JWT_SECRET=_VALID_JWT,
        FIRST_ADMIN_PASSWORD="admin123",
    )
    result = _run_bootstrap(env, cwd=str(tmp_path))

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "FIRST_ADMIN_PASSWORD" in combined
