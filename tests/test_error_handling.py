"""
Tests for how backend error bodies are turned into exceptions and messages.

This is the layer that decides whether a caller sees the backend's actionable text or a
generic "Request failed with status 400". DRF reports validation errors as
{"field": ["message"]}, so the useful wording arrives under a field name rather than
"detail" - reading only the well-known keys threw it away.
"""

from __future__ import annotations

import httpx
import pytest

from google_integration_proxy import (
    GoogleIntegrationAccountError,
    GoogleIntegrationAPIError,
    GoogleIntegrationAuthError,
    GoogleIntegrationClient,
    GoogleIntegrationNotFoundError,
)

UNBOUND_BODY = {
    "google_account": [
        "API client 'Acme' has no Google account bound. Set one in admin: "
        "Google Integration -> Google Integration Clients -> Acme -> Google account."
    ]
}
REVOKED_BODY = {
    "detail": [
        "Google rejected the refresh token for 'a@example.com'. The token was likely "
        "revoked or expired; reconnect the account via /api/google/oauth/start/."
    ]
}


def make_client(handler) -> GoogleIntegrationClient:
    """Client wired to a mock transport, so nothing touches the network."""
    client = GoogleIntegrationClient("http://backend.test", api_key="k" * 40)
    client._client = httpx.Client(
        base_url="http://backend.test", transport=httpx.MockTransport(handler)
    )
    return client


def responder(status: int, body):
    return lambda request: httpx.Response(status, json=body)


class TestErrorClassification:
    def test_unbound_client_raises_account_error(self):
        client = make_client(responder(400, UNBOUND_BODY))
        with pytest.raises(GoogleIntegrationAccountError) as exc:
            client.create_event("x", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z")
        # The backend's remedy must survive into the exception message.
        assert "has no Google account bound" in str(exc.value)
        assert "Google Integration Clients" in str(exc.value)
        assert exc.value.status_code == 400
        assert exc.value.body == UNBOUND_BODY

    def test_revoked_token_raises_account_error(self):
        client = make_client(responder(400, REVOKED_BODY))
        with pytest.raises(GoogleIntegrationAccountError) as exc:
            client.create_event("x", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z")
        assert "reconnect the account" in str(exc.value)

    def test_disabled_account_raises_account_error(self):
        body = {
            "google_account": [
                "Google account 'a@example.com' bound to client 'Acme' is disabled."
            ]
        }
        client = make_client(responder(400, body))
        with pytest.raises(GoogleIntegrationAccountError):
            client.create_event("x", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z")

    def test_ordinary_validation_error_is_not_an_account_error(self):
        """A plain bad-input 400 must stay a generic API error."""
        body = {"start": ["Datetime has wrong format."]}
        client = make_client(responder(400, body))
        with pytest.raises(GoogleIntegrationAPIError) as exc:
            client.create_event("x", "nonsense", "nonsense")
        assert not isinstance(exc.value, GoogleIntegrationAccountError)
        assert "Datetime has wrong format" in str(exc.value)

    def test_account_error_is_catchable_as_api_error(self):
        """Existing `except GoogleIntegrationAPIError` handlers keep working."""
        client = make_client(responder(400, UNBOUND_BODY))
        with pytest.raises(GoogleIntegrationAPIError):
            client.create_event("x", "2026-01-01T10:00:00Z", "2026-01-01T10:30:00Z")

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_errors(self, status):
        client = make_client(responder(status, {"detail": "Invalid API key."}))
        with pytest.raises(GoogleIntegrationAuthError) as exc:
            client.list_events()
        assert "Invalid API key" in str(exc.value)

    def test_404_raises_not_found(self):
        client = make_client(
            responder(404, {"detail": "No event found with meeting code 'zzz'."})
        )
        with pytest.raises(GoogleIntegrationNotFoundError) as exc:
            client.get_event(999)
        assert "No event found" in str(exc.value)

    def test_500_raises_generic_api_error(self):
        client = make_client(responder(500, None))
        with pytest.raises(GoogleIntegrationAPIError) as exc:
            client.list_events()
        assert exc.value.status_code == 500
        assert "500" in str(exc.value)


class TestErrorMessageParsing:
    """The message builder in isolation, including shapes we do not yet emit."""

    def test_field_keyed_errors_are_flattened(self):
        msg = GoogleIntegrationClient._error_message(400, UNBOUND_BODY)
        assert msg.startswith("google_account: API client 'Acme'")
        assert "Request failed" not in msg

    def test_detail_list_is_joined_not_stringified(self):
        msg = GoogleIntegrationClient._error_message(400, REVOKED_BODY)
        # Must not leak Python list syntax into a user-facing message.
        assert not msg.startswith("[")
        assert "'" != msg[0]
        assert "Google rejected the refresh token" in msg

    def test_account_field_wins_over_other_fields(self):
        body = {"summary": ["Too long."], "google_account": ["No account bound."]}
        msg = GoogleIntegrationClient._error_message(400, body)
        assert msg.startswith("google_account:")

    def test_nested_dict_is_flattened(self):
        body = {"attendees": [{"email": ["Enter a valid email address."]}]}
        msg = GoogleIntegrationClient._error_message(400, body)
        assert "Enter a valid email address" in msg

    def test_empty_body_falls_back_to_status(self):
        assert "409" in GoogleIntegrationClient._error_message(409, None)
        assert "409" in GoogleIntegrationClient._error_message(409, {})

    def test_enveloped_error_body(self):
        body = {"data": {"detail": "Wrapped message."}}
        assert GoogleIntegrationClient._error_message(400, body) == "Wrapped message."
