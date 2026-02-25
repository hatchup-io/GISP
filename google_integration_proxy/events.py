"""Calendar events proxy for the Google-integration backend."""

from __future__ import annotations

from google_integration_proxy.client import GoogleIntegrationClient


class EventsService:
    """Service for calendar events API (list, create, get, update, delete)."""

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
        """Create a calendar event. Optionally syncs to Google and adds Meet link."""
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
        self._client._request(
            "DELETE",
            f"api/google/events/{event_id}/",
            require_auth=True,
        )
