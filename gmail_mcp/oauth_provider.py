import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

STATE_PATH = Path(os.environ.get("GMAIL_MCP_OAUTH_STATE", "secrets/oauth_state.json"))
PASSPHRASE = os.environ["GMAIL_MCP_OAUTH_PASSPHRASE"]
CLIENT_ID = os.environ["GMAIL_MCP_OAUTH_CLIENT_ID"]
REDIRECT_URIS = [u.strip() for u in os.environ["GMAIL_MCP_OAUTH_REDIRECT_URIS"].split(",") if u.strip()]
ISSUER = os.environ["GMAIL_MCP_ISSUER_URL"]
DEFAULT_SCOPES = ["gmail.readonly", "gmail.compose"]
ACCESS_TOKEN_TTL = 3600
PENDING_TTL = 600
CODE_TTL = 300


def _empty_state() -> dict[str, Any]:
    return {"pending": {}, "codes": {}, "access_tokens": {}, "refresh_tokens": {}}


def _load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return _empty_state()


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state))


class GmailOAuthProvider(OAuthAuthorizationServerProvider):
    def __init__(self) -> None:
        self._client = OAuthClientInformationFull(
            client_id=CLIENT_ID,
            redirect_uris=REDIRECT_URIS,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
            scope=" ".join(DEFAULT_SCOPES),
        )

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._client if client_id == CLIENT_ID else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        raise NotImplementedError("dynamic client registration is disabled")

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        state = _load_state()
        txn = secrets.token_urlsafe(24)
        state["pending"][txn] = {
            "client_id": client.client_id,
            "state": params.state,
            "scopes": DEFAULT_SCOPES,
            "code_challenge": params.code_challenge,
            "redirect_uri": str(params.redirect_uri),
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "resource": ISSUER,
            "expires_at": int(time.time()) + PENDING_TTL,
        }
        _save_state(state)
        return f"/consent?txn={txn}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        rec = _load_state()["codes"].get(authorization_code)
        if not rec or rec["client_id"] != client.client_id or rec["expires_at"] < time.time():
            return None
        return AuthorizationCode(**rec)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        state = _load_state()
        rec = state["codes"].pop(authorization_code.code, None)
        if rec is None:
            raise TokenError("invalid_grant", "authorization code already used or unknown")
        _save_state(state)
        return self._issue_tokens(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rec = _load_state()["refresh_tokens"].get(refresh_token)
        if not rec or rec["client_id"] != client.client_id:
            return None
        return RefreshToken(**rec)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        state = _load_state()
        state["refresh_tokens"].pop(refresh_token.token, None)
        _save_state(state)
        return self._issue_tokens(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        rec = _load_state()["access_tokens"].get(token)
        if not rec:
            return None
        if rec["expires_at"] is not None and rec["expires_at"] < time.time():
            return None
        return AccessToken(**rec)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        state = _load_state()
        state["access_tokens"].pop(getattr(token, "token", None), None)
        state["refresh_tokens"].pop(getattr(token, "token", None), None)
        _save_state(state)

    def _issue_tokens(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        state = _load_state()
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        now = int(time.time())
        state["access_tokens"][access_token] = {
            "token": access_token,
            "client_id": client_id,
            "scopes": scopes,
            "expires_at": now + ACCESS_TOKEN_TTL,
            "resource": resource,
        }
        state["refresh_tokens"][refresh_token] = {
            "token": refresh_token,
            "client_id": client_id,
            "scopes": scopes,
            "expires_at": None,
            "resource": resource,
        }
        _save_state(state)
        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL,
            scope=" ".join(scopes) if scopes else None,
            refresh_token=refresh_token,
        )


def pop_pending(txn: str) -> dict[str, Any] | None:
    state = _load_state()
    rec = state["pending"].pop(txn, None)
    _save_state(state)
    if not rec or rec["expires_at"] < time.time():
        return None
    return rec


def peek_pending(txn: str) -> dict[str, Any] | None:
    rec = _load_state()["pending"].get(txn)
    if not rec or rec["expires_at"] < time.time():
        return None
    return rec


def check_passphrase(value: str) -> bool:
    return secrets.compare_digest(value, PASSPHRASE)


def issue_code_and_redirect(pending: dict[str, Any]) -> str:
    state = _load_state()
    code = secrets.token_urlsafe(32)
    state["codes"][code] = {
        "code": code,
        "scopes": pending["scopes"],
        "expires_at": int(time.time()) + CODE_TTL,
        "client_id": pending["client_id"],
        "code_challenge": pending["code_challenge"],
        "redirect_uri": pending["redirect_uri"],
        "redirect_uri_provided_explicitly": pending["redirect_uri_provided_explicitly"],
        "resource": pending["resource"],
    }
    _save_state(state)
    return construct_redirect_uri(pending["redirect_uri"], code=code, state=pending["state"])
