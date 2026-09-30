import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger("gmail_mcp")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CREDENTIALS_PATH = Path(os.environ.get("GMAIL_MCP_CREDENTIALS", "credentials.json"))
TOKEN_PATH = Path(os.environ.get("GMAIL_MCP_TOKEN", "token.json"))


def load_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
            logger.info("token_refreshed")
        except Exception:
            logger.exception("token_refresh_failed")
            raise

    if not creds or not creds.valid:
        logger.error("no_valid_credentials path=%s", TOKEN_PATH)
        raise RuntimeError(
            f"No valid credentials at {TOKEN_PATH}. Run `python authorize.py` first."
        )

    return creds


def run_authorization_flow() -> None:
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            f"{CREDENTIALS_PATH} not found. Download a Desktop OAuth client "
            "from the Google Cloud Console and save it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved credentials to {TOKEN_PATH}")
