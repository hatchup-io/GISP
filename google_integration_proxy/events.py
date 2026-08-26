"""Calendar events proxy for the Google-integration backend."""

from __future__ import annotations

from google_integration_proxy.client import GoogleIntegrationClient


class EventsService:
    """
    Service for calendar events API (list, create, get, update, delete).

    Every call is scoped to the Google account bound to the client's API key, and results
    report it as ``google_account_email``. See ``GoogleIntegrationClient`` for what that
    implies about visibility across keys.
    """

    def __init__(self, client: GoogleIntegrationClient) -> None:
        self._client = client

    def list(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        raw: bool = False,
    ) -> dict | list:
        """List calendar events for the authenticated API client."""
        params: dict[str, int] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        result = self._client._request(
            "GET",
            "api/google/events/",
            params=params or None,
            require_auth=True,
            raw=raw,
        )
        return result if result is not None else []

    def create(
        self,
        summary: str,
        start: str,
        end: str,
        *,
        description: str = "",
        time_zone: str = "UTC",
        attendees: list[dict] | None = None,
        raw: bool = False,
    ) -> dict | None:
        """Create a calendar event with a Google Meet link.

        Books on the account bound to this client's API key. The backend creates the local
        record and the Google event in one transaction, so a Google failure leaves nothing
        behind and raises rather than returning a half-created event.
        """
        payload: dict = {
            "summary": summary,
            "start": start,
            "end": end,
            "time_zone": time_zone,
        }
        if description:
            payload["description"] = description
        if attendees:
            payload["attendees"] = attendees
        result = self._client._request(
            "POST",
            "api/google/events/",
            json=payload,
            require_auth=True,
            raw=raw,
        )
        return result if isinstance(result, dict) else None

    def check_held(self, event_id: int | str, *, raw: bool = False) -> dict | None:
        """Check whether an event's Meet session was held, by **numeric event id**.

        Queries the backend, which calls the Google Meet API as the account that booked
        the event, persists the result, and returns the updated event (was_held,
        participant_count, etc.).

        ``event_id`` is the ``id`` field, not ``meeting_code`` or ``google_event_id``;
        passing either of those raises ``GoogleIntegrationNotFoundError``. Use
        ``check_held_by_code`` for a meeting code.
        """
        result = self._client._request(
            "POST",
            f"api/google/events/{event_id}/check-held/",
            require_auth=True,
            raw=raw,
        )
        return result if isinstance(result, dict) else None

    def check_held_by_code(
        self, meeting_code: str, *, raw: bool = False
    ) -> dict | None:
        """Check whether a Meet session was held, locating the event by meeting code
        (e.g. "abc-defg-hij").

        Returns the updated event dict. Raises ``GoogleIntegrationNotFoundError`` if no
        event with that code is visible to this API key - which includes codes belonging
        to another key's account. Use ``GoogleIntegrationClient.is_session_held`` for a
        boolean that treats not-found as "not held".
        """
        result = self._client._request(
            "POST",
            "api/google/events/check-held-by-code/",
            params={"meeting_code": meeting_code},
            require_auth=True,
            raw=raw,
        )
        return result if isinstance(result, dict) else None

    def get(self, event_id: int | str, *, raw: bool = False) -> dict | None:
        """Retrieve a calendar event by ID."""
        result = self._client._request(
            "GET",
            f"api/google/events/{event_id}/",
            require_auth=True,
            raw=raw,
        )
        return result if isinstance(result, dict) else None

    def update(
        self,
        event_id: int | str,
        *,
        partial: bool = True,
        raw: bool = False,
        **kwargs: str | list[dict] | None,
    ) -> dict | None:
        """Update a calendar event. Pass fields to update as keyword arguments."""
        if not kwargs:
            return self.get(event_id, raw=raw)
        method = "PATCH" if partial else "PUT"
        result = self._client._request(
            method,
            f"api/google/events/{event_id}/",
            json=kwargs,
            require_auth=True,
            raw=raw,
        )
        return result if isinstance(result, dict) else None

    def delete(self, event_id: int | str) -> None:
        """Soft-delete a calendar event; cancels on Google if synced."""
        result = self._client._request(
            "DELETE",
            f"api/google/events/{event_id}/",
            require_auth=True,
        )
        return result if isinstance(result, dict) else None
