import os

from starlette.routing import Route

from mcp.server.transport_security import TransportSecuritySettings

from .consent import consent_get, consent_post
from .server import mcp

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("GMAIL_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]

transport_security = (
    TransportSecuritySettings(allowed_hosts=ALLOWED_HOSTS) if ALLOWED_HOSTS else None
)
app = mcp.streamable_http_app(transport_security=transport_security)
app.router.routes.extend(
    [
        Route("/consent", consent_get, methods=["GET"]),
        Route("/consent", consent_post, methods=["POST"]),
    ]
)
