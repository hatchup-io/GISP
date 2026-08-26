"""
Tests for account awareness and the availability helpers.

The contract under test: the API key selects the Google account, the response reports it,
and a caller can ask whether the backend is able to book before trying.
"""

from __future__ import annotations

import httpx
import pytest

from google_integration_proxy import GoogleIntegrationAccountError
from tests.test_error_handling import make_client, responder


def event_body(account: str = "bookings@example.com", **over) -> dict:
    payload = {
        "id": 7,
        "google_event_id": "abc123",
        "google_account_email": account,
        "summary": "Standup",
        "start": "2026-09-20T10:00:00Z",
        "end": "2026-09-20T10:30:00Z",
        "time_zone": "UTC",
        "meet_link": "https://meet.google.com/abc-defg-hij",
        "meeting_code": "abc-defg-hij",
        "is_synced": True,
        "was_held": None,
        "participant_count": None,
        "attendees": [],
    }
    payload.update(over)
    return payload


def envelope(data) -> dict:
    return {
        "message": "Request was successful",
        "status": 200,
        "pagination": None,
        "data": data,
    }


class TestAccountReporting:
    def test_create_reports_the_booking_account(self):
        client = make_client(responder(201, envelope(event_body("team-a@example.com"))))
        event = client.create_event(
            "Standup", "2026-09-20T10:00:00Z", "2026-09-20T10:30:00Z"
        )
        assert event["google_account_email"] == "team-a@example.com"

    def test_account_field_in_payload_is_not_sent_as_a_choice(self):
        """The key selects the account; the client must not invent a way to override it."""
        sent = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent["content"] = request.content.decode()
            return httpx.Response(201, json=envelope(event_body()))

        client = make_client(handler)
        client.create_event("Standup", "2026-09-20T10:00:00Z", "2026-09-20T10:30:00Z")
        assert "google_account" not in sent["content"]

    def test_api_key_header_is_sent(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["key"] = request.headers.get("X-API-Key")
            return httpx.Response(200, json=envelope([]))

        client = make_client(handler)
        client.list_events()
        assert seen["key"] == "k" * 40


class TestIsSessionHeld:
    def test_true_when_held_with_enough_participants(self):
        client = make_client(
            responder(200, envelope(event_body(was_held=True, participant_count=3)))
        )
        assert client.is_session_held("abc-defg-hij") is True

    def test_false_when_too_few_participants(self):
        client = make_client(
            responder(200, envelope(event_body(was_held=True, participant_count=2)))
        )
        assert client.is_session_held("abc-defg-hij") is False

    def test_false_when_not_held(self):
        client = make_client(
            responder(200, envelope(event_body(was_held=False, participant_count=None)))
        )
        assert client.is_session_held("abc-defg-hij") is False

    def test_false_when_code_is_unknown(self):
        """Documented as returning False for not-found; it used to raise instead."""
        client = make_client(
            responder(
                404, {"detail": "No event found with meeting code 'zzz-zzzz-zzz'."}
            )
        )
        assert client.is_session_held("zzz-zzzz-zzz") is False

    def test_account_faults_still_raise(self):
        """A broken binding is a fault to fix, not a "not held" answer."""
        client = make_client(
            responder(400, {"google_account": ["No Google account bound."]})
        )
        with pytest.raises(GoogleIntegrationAccountError):
            client.is_session_held("abc-defg-hij")

    def test_custom_threshold(self):
        client = make_client(
            responder(200, envelope(event_body(was_held=True, participant_count=5)))
        )
        assert client.is_session_held("abc-defg-hij", min_participants=6) is False
        assert client.is_session_held("abc-defg-hij", min_participants=5) is True


def readiness_payload(status: str, **details) -> dict:
    return envelope(
        {
            "status": status,
            "environment": "test",
            "services": {
                "google_integration": {
                    "name": "google_integration",
                    "status": status,
                    "message": "…",
                    "details": details or {"accounts_bookable": 1},
                }
            },
        }
    )


class TestAvailability:
    def test_health_is_unauthenticated(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["key"] = request.headers.get("X-API-Key")
            seen["path"] = request.url.path
            return httpx.Response(200, json=envelope({"status": "ok"}))

        client = make_client(handler)
        assert client.health()["status"] == "ok"
        assert seen["path"] == "/api/health/"
        assert seen["key"] is None

    def test_status_extracts_the_google_check(self):
        client = make_client(responder(200, readiness_payload("healthy")))
        check = client.google_integration_status()
        assert check["status"] == "healthy"
        assert check["details"]["accounts_bookable"] == 1

    def test_available_only_when_healthy(self):
        for status, expected in [
            ("healthy", True),
            ("degraded", False),
            ("unhealthy", False),
        ]:
            client = make_client(responder(200, readiness_payload(status)))
            assert client.is_google_integration_available() is expected, status

    def test_status_readable_from_a_503_body(self):
        """Readiness answers 503 when unhealthy; the reason is in the body, not lost."""
        client = make_client(responder(503, readiness_payload("unhealthy")))
        check = client.google_integration_status()
        assert check is not None
        assert check["status"] == "unhealthy"
        assert client.is_google_integration_available() is False

    def test_unreachable_backend_is_unavailable_not_an_exception(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = make_client(handler)
        assert client.is_google_integration_available() is False

    def test_missing_google_section_returns_none(self):
        client = make_client(responder(200, envelope({"services": {}})))
        assert client.google_integration_status() is None
        assert client.is_google_integration_available() is False
