"""HTTP client for the Google-integration backend (API key auth, response envelope)."""

from __future__ import annotations

import httpx

from google_integration_proxy.exceptions import (
    GoogleIntegrationAPIError,
    GoogleIntegrationAuthError,
)


class GoogleIntegrationClient:
    """
    Sync client for the Google-integration backend calendar events API.
    Uses API key auth (X-API-Key or Authorization: Api-Key <key>).
    """

    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=30.0,
        )

    def _headers(self, require_auth: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if require_auth and self._api_key:
            headers["X-API-Key"] = self._api_key
            headers["Authorization"] = f"Api-Key {self._api_key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        require_auth: bool = True,
        raw: bool = False,
    ) -> dict | list | None:
        path_str = path.lstrip("/")
        headers = self._headers(require_auth=require_auth)
        response = self._client.request(
            method,
            path_str,
            json=json,
            params=params,
            headers=headers,
        )

        if response.status_code in (204, 205):
            return None

        try:
            body = response.json()
        except Exception:
            body = None

        if response.status_code >= 400:
            msg = self._error_message(response.status_code, body)
            if response.status_code in (401, 403):
                raise GoogleIntegrationAuthError(
                    msg, status_code=response.status_code, body=body
                )
            raise GoogleIntegrationAPIError(
                msg, status_code=response.status_code, body=body
            )

        if raw:
            return body
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    @staticmethod
    def _error_message(status_code: int, body: dict | list | None) -> str:
        if isinstance(body, dict):
            for key in ("detail", "message", "error"):
                if key in body and body[key]:
                    val = body[key]
                    return val if isinstance(val, str) else str(val)
            if "data" in body and isinstance(body.get("data"), dict):
                for key in ("detail", "message", "error"):
                    if key in body["data"] and body["data"][key]:
                        return str(body["data"][key])
        return f"Request failed with status {status_code}"

    @property
    def events(self) -> "EventsService":
        """Calendar events service (list, create, get, update, delete)."""
        from google_integration_proxy.events import EventsService

        return EventsService(self)

    def list_events(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        raw: bool = False,
    ) -> dict | list:
        """List calendar events for the authenticated API client."""
        return self.events.list(page=page, page_size=page_size, raw=raw)

    def create_event(
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
        return self.events.create(
            summary,
            start,
            end,
            description=description,
            time_zone=time_zone,
            attendees=attendees,
            raw=raw,
        )

    def get_event(self, event_id: int | str, *, raw: bool = False) -> dict | None:
        """Retrieve a calendar event by ID."""
        return self.events.get(event_id, raw=raw)

    def update_event(
        self,
        event_id: int | str,
        *,
        partial: bool = True,
        raw: bool = False,
        **kwargs: str | list[dict] | None,
    ) -> dict | None:
        """Update a calendar event. Pass fields to update as keyword arguments."""
        return self.events.update(event_id, partial=partial, raw=raw, **kwargs)

    def delete_event(self, event_id: int | str) -> None:
        """Soft-delete a calendar event; cancels on Google if synced."""
        self.events.delete(event_id)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GoogleIntegrationClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
