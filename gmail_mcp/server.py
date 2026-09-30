import functools
import logging
import os

from mcp.server.mcpserver import MCPServer

from . import gmail_client

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("gmail_mcp")


def _brief(kwargs: dict) -> dict:
    return {
        k: (v[:100] + "…" if isinstance(v, str) and len(v) > 100 else v)
        for k, v in kwargs.items()
    }


def _logged(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        logger.info("tool_call name=%s args=%s", fn.__name__, _brief(kwargs))
        try:
            result = fn(*args, **kwargs)
            logger.info("tool_ok name=%s", fn.__name__)
            return result
        except Exception:
            logger.exception("tool_error name=%s", fn.__name__)
            raise
    return wrapper


def _build_mcp() -> MCPServer:
    if os.environ.get("GMAIL_MCP_ENABLE_OAUTH") != "1":
        return MCPServer("gmail")

    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

    from .oauth_provider import GmailOAuthProvider

    issuer = os.environ["GMAIL_MCP_ISSUER_URL"]
    return MCPServer(
        "gmail",
        auth_server_provider=GmailOAuthProvider(),
        auth=AuthSettings(
            issuer_url=issuer,
            client_registration_options=ClientRegistrationOptions(enabled=False),
            required_scopes=["gmail.readonly", "gmail.compose"],
            resource_server_url=issuer,
            validate_token_resource=True,
        ),
    )


mcp = _build_mcp()


@mcp.tool()
@_logged
def gmail_search(query: str, max_results: int = 10) -> list[dict]:
    """Search Gmail messages using the Gmail search syntax (e.g. 'from:x@y.com is:unread')."""
    return gmail_client.search_messages(query, max_results)


@mcp.tool()
@_logged
def gmail_get_message(message_id: str) -> dict:
    """Fetch a single Gmail message by id, including its plain-text body."""
    return gmail_client.get_message(message_id)


@mcp.tool()
@_logged
def gmail_get_thread(thread_id: str) -> dict:
    """Fetch every message in a Gmail thread by thread id."""
    return gmail_client.get_thread(thread_id)


@mcp.tool()
@_logged
def gmail_create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    reply_to_message_id: str = "",
) -> dict:
    """Create a Gmail draft. Never sends anything, the draft sits in Drafts for the
    user to review and send themselves. Set reply_to_message_id to draft a reply
    within an existing thread (sets In-Reply-To/References/threadId correctly)."""
    return gmail_client.create_draft(
        to,
        subject,
        body,
        cc=cc or None,
        bcc=bcc or None,
        reply_to_message_id=reply_to_message_id or None,
    )


@mcp.tool()
@_logged
def gmail_list_labels() -> list[dict]:
    """List all Gmail labels on the account."""
    return gmail_client.list_labels()


@mcp.tool()
@_logged
def gmail_modify_labels(
    message_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None
) -> dict:
    """Add or remove labels (by name, e.g. 'outreach') on a message. Works on drafts too:
    pass the draft's messageId (from gmail_create_draft), since a draft is a message with
    the DRAFT label. Labels must already exist; check gmail_list_labels first."""
    return gmail_client.modify_labels(message_id, add_labels, remove_labels)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
