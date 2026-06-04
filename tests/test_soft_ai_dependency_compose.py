from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _compose_service(compose: str, service_name: str, next_service: str) -> str:
    return compose.split(f"  {service_name}:", 1)[1].split(f"  {next_service}:", 1)[0]


def test_api_and_worker_do_not_wait_on_ollama_health_to_boot() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    api_service = _compose_service(compose, "api", "worker")
    worker_service = _compose_service(compose, "worker", "beat")

    assert "ollama/ollama:latest" in compose
    for service in (api_service, worker_service):
        depends_on = service.split("depends_on:", 1)[1].split("healthcheck:", 1)[0]
        assert "postgres:" in depends_on
        assert "redis:" in depends_on
        assert "condition: service_healthy" in depends_on
        assert "ollama:" not in depends_on
