#!/usr/bin/env python3
"""Build and install CivicSunshine in a fresh virtualenv, then prove app import."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd, env=env)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="civicrecords-runtime-install-") as tmp:
        tmpdir = Path(tmp)
        build_venv = tmpdir / "build-venv"
        install_venv = tmpdir / "install-venv"
        venv.EnvBuilder(with_pip=True).create(build_venv)
        venv.EnvBuilder(with_pip=True).create(install_venv)

        build_python = build_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        install_python = install_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        dist = BACKEND / "dist"
        if dist.exists():
            shutil.rmtree(dist)

        run([str(build_python), "-m", "pip", "install", "--upgrade", "pip", "build"], cwd=BACKEND)
        run([str(build_python), "-m", "build"], cwd=BACKEND)

        wheels = sorted(dist.glob("*.whl"))
        if not wheels:
            print("RUNTIME-INSTALL-PROOF: FAILED - no wheel produced")
            return 1

        run([str(install_python), "-m", "pip", "install", str(wheels[-1])], cwd=BACKEND)

        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": "postgresql+asyncpg://civicrecords:civicrecords@127.0.0.1:5432/civicrecords_runtime_proof",
                "JWT_SECRET": "runtimeproof" * 4,
                "FIRST_ADMIN_EMAIL": "admin@example.gov",
                "FIRST_ADMIN_PASSWORD": "RuntimeProofPassword2026",
                "ENCRYPTION_KEY": "7_NU0Qmw5LeUDWM1PNvFNQzOA-qI5sU-NWbYUkRSCIM=",
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "REDIS_URL": "redis://127.0.0.1:6379/0",
                "AUDIT_RETENTION_DAYS": "1095",
                "PORTAL_MODE": "private",
                "TESTING": "1",
            }
        )
        run(
            [
                str(install_python),
                "-c",
                "from app.main import app; "
                "from fastapi.testclient import TestClient; "
                "r=TestClient(app).get('/health'); "
                "assert r.status_code == 200, r.text; "
                "print('RUNTIME-INSTALL-PROOF: health', r.json())",
            ],
            cwd=tmpdir,
            env=env,
        )

    print("RUNTIME-INSTALL-PROOF: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
