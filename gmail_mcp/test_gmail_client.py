"""Runnable self-check for label name resolution. python -m gmail_mcp.test_gmail_client"""
from unittest.mock import MagicMock, patch

from .gmail_client import modify_labels


def _service_with_labels(labels: list[dict]) -> MagicMock:
    service = MagicMock()
    service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": labels
    }
    return service


def test_modify_labels_resolves_names_to_ids():
    service = _service_with_labels([{"id": "L1", "name": "outreach"}, {"id": "DRAFT", "name": "DRAFT"}])
    service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {
        "id": "msg1",
        "labelIds": ["L1", "DRAFT"],
    }

    with patch("gmail_mcp.gmail_client.get_service", return_value=service):
        result = modify_labels("msg1", add_labels=["outreach"], remove_labels=[])

    service.users.return_value.messages.return_value.modify.assert_called_once_with(
        userId="me", id="msg1", body={"addLabelIds": ["L1"], "removeLabelIds": []}
    )
    assert result == {"id": "msg1", "labelIds": ["L1", "DRAFT"]}


def test_modify_labels_rejects_unknown_name():
    service = _service_with_labels([{"id": "L1", "name": "outreach"}])

    with patch("gmail_mcp.gmail_client.get_service", return_value=service):
        try:
            modify_labels("msg1", add_labels=["does-not-exist"])
            assert False, "expected ValueError for unknown label"
        except ValueError as e:
            assert "does-not-exist" in str(e)


if __name__ == "__main__":
    test_modify_labels_resolves_names_to_ids()
    test_modify_labels_rejects_unknown_name()
    print("ok")
