"""Runnable self-check for the _logged decorator and /health endpoint. python -m gmail_mcp.test_observability"""
import asyncio
from unittest.mock import patch

from .server import _logged
from .http_app import health


def test_logged_passes_through_result():
    @_logged
    def ok(x):
        return x * 2

    assert ok(21) == 42


def test_logged_reraises_and_does_not_swallow():
    @_logged
    def boom():
        raise ValueError("nope")

    try:
        boom()
        assert False, "expected ValueError to propagate"
    except ValueError:
        pass


def test_health_ok():
    with patch("gmail_mcp.http_app.gmail_client.get_service") as mock_service:
        mock_service.return_value.users.return_value.getProfile.return_value.execute.return_value = {}
        resp = asyncio.run(health(request=None))
        assert resp.status_code == 200


def test_health_reports_failure():
    with patch("gmail_mcp.http_app.gmail_client.get_service", side_effect=RuntimeError("no token")):
        resp = asyncio.run(health(request=None))
        assert resp.status_code == 503


if __name__ == "__main__":
    test_logged_passes_through_result()
    test_logged_reraises_and_does_not_swallow()
    test_health_ok()
    test_health_reports_failure()
    print("ok")
