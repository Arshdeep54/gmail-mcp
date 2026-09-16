import os

from mcp.server.mcpserver import MCPServer

from . import gmail_client


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
def gmail_search(query: str, max_results: int = 10) -> list[dict]:
    """Search Gmail messages using the Gmail search syntax (e.g. 'from:x@y.com is:unread')."""
    return gmail_client.search_messages(query, max_results)


@mcp.tool()
def gmail_get_message(message_id: str) -> dict:
    """Fetch a single Gmail message by id, including its plain-text body."""
    return gmail_client.get_message(message_id)


@mcp.tool()
def gmail_get_thread(thread_id: str) -> dict:
    """Fetch every message in a Gmail thread by thread id."""
    return gmail_client.get_thread(thread_id)


@mcp.tool()
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
def gmail_list_labels() -> list[dict]:
    """List all Gmail labels on the account."""
    return gmail_client.list_labels()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
