import os

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp.server.transport_security import TransportSecuritySettings

from . import gmail_client
from .consent import consent_get, consent_post
from .server import logger, mcp

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("GMAIL_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]

transport_security = (
    TransportSecuritySettings(allowed_hosts=ALLOWED_HOSTS) if ALLOWED_HOSTS else None
)
app = mcp.streamable_http_app(transport_security=transport_security)


async def health(request: Request) -> JSONResponse:
    """Confirms the Gmail token is valid and the API is reachable, not just that the process is up."""
    try:
        gmail_client.get_service().users().getProfile(userId="me").execute(num_retries=3)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.exception("health_check_failed")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


app.router.routes.extend(
    [
        Route("/consent", consent_get, methods=["GET"]),
        Route("/consent", consent_post, methods=["POST"]),
        Route("/health", health, methods=["GET"]),
    ]
)
