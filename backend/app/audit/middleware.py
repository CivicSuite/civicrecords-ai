import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.audit.logger import write_audit_log
from app.database import async_session_maker

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        response = await call_next(request)

        user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None

        try:
            async with async_session_maker() as session:
                await write_audit_log(
                    session=session,
                    action=f"{request.method} {request.url.path}",
                    resource_type="http_request",
                    resource_id=request.url.path,
                    user_id=user_id,
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "query": str(request.url.query) if request.url.query else None,
                        "status_code": response.status_code,
                        "client_ip": request.client.host if request.client else None,
                    },
                )
        except Exception:
            pass

        return response
