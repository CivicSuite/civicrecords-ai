from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="CivicRecords AI",
        description="AI-powered open records support for American cities",
        version="0.1.0",
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
