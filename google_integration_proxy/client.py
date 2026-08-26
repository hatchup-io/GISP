"""HTTP client for the Google-integration backend (API key auth, response envelope)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import httpx

from google_integration_proxy.exceptions import (
    GoogleIntegrationAccountError,
    GoogleIntegrationAPIError,
    GoogleIntegrationAuthError,
    GoogleIntegrationNotFoundError,
)

if TYPE_CHECKING:
    # Runtime import stays inside `events` property to avoid a circular import.
    from google_integration_proxy.events import EventsService

# Field names the backend uses for account-configuration faults, which are raised as
# GoogleIntegrationAccountError rather than a generic API error.
_ACCOUNT_ERROR_FIELDS = ("google_account", "google_account_email")

# Substrings identifying an account fault reported under a generic "detail" key.
_ACCOUNT_ERROR_HINTS = (
    "no google account bound",
    "has no refresh token",
    "refresh token for",
    "reconnect the account",
    "is disabled",
)


# Base URLs by environment (env ENV or ENVIRONMENT)
STAGING_BASE_URL = "https://api.google-integration.service.staging.hatchup.capital"
PRODUCTION_BASE_URL = "https://api.google-integration.service.hatchup.capital"
LOCAL_BASE_URL_ENV_VAR = "GOOGLE_INTEGRATION_BASE_URL"


def get_base_url_from_env() -> str:
    """
    Resolve base URL from environment.
    Reads ENV or ENVIRONMENT; for 'staging'/'production' returns fixed URLs,
    for 'local' (or missing) returns GOOGLE_INTEGRATION_BASE_URL.
    """
    env = (
        (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "local")
        .strip()
        .lower()
    )
    if env == "staging":
        return STAGING_BASE_URL
    if env == "production":
        return PRODUCTION_BASE_URL
    base_url = os.environ.get(LOCAL_BASE_URL_ENV_VAR, "").strip()
    if not base_url:
        raise ValueError(
            f"For local environment set {LOCAL_BASE_URL_ENV_VAR}; "
            "or set ENV=staging|production to use a fixed base URL."
        )
    return base_url.rstrip("/")


class GoogleIntegrationClient:
    """
    Sync client for the Google-integration backend calendar events API.
    Uses API key auth (X-API-Key or Authorization: Api-Key <key>).

    **The API key determines which Google account events are booked on.** The backend
    binds each API client to one Google account, so a key is effectively a handle to a
    calendar; there is no request field to choose one. Responses report the account that
    was used as ``google_account_email``.

    Consequences worth knowing:

    - Events are scoped to the key that created them. Listing with one key never returns
      another key's events, and fetching another key's event by id raises
      ``GoogleIntegrationNotFoundError``.
    - To book on several calendars, hold several keys and pick the client per calendar.
    - Account misconfiguration (no account bound, disabled account, revoked token) raises
      ``GoogleIntegrationAccountError``; retrying will not help until the backend is fixed.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
    ) -> None:
        if base_url is None:
            base_url = get_base_url_from_env()
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
            if response.status_code == 404:
                raise GoogleIntegrationNotFoundError(
                    msg, status_code=response.status_code, body=body
                )
            if self._is_account_error(response.status_code, body):
                raise GoogleIntegrationAccountError(
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
    def _flatten(value: object) -> str:
        """Render a DRF error value (str, list of str, or nested dict) as one line."""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return " ".join(GoogleIntegrationClient._flatten(v) for v in value if v)
        if isinstance(value, dict):
            return " ".join(
                f"{k}: {GoogleIntegrationClient._flatten(v)}"
                for k, v in value.items()
                if v
            )
        return str(value)

    @staticmethod
    def _error_message(status_code: int, body: dict | list | None) -> str:
        """
        Build a human-readable message from an error body.

        DRF reports validation errors as {"field": ["message", ...]}, so the backend's
        actionable text (for example "API client 'x' has no Google account bound") arrives
        under a field name rather than "detail". Reading only the well-known keys reduced
        those to "Request failed with status 400" and threw the useful part away.
        """
        if isinstance(body, dict):
            for key in ("detail", "message", "error"):
                if body.get(key):
                    return GoogleIntegrationClient._flatten(body[key])
            data = body.get("data")
            if isinstance(data, dict):
                for key in ("detail", "message", "error"):
                    if data.get(key):
                        return GoogleIntegrationClient._flatten(data[key])
            # Fall back to field-keyed validation errors, account fields first so the
            # most actionable message wins when several fields failed.
            ordered = sorted(
                (k for k, v in body.items() if v and k not in ("data",)),
                key=lambda k: (k not in _ACCOUNT_ERROR_FIELDS, k),
            )
            parts = [
                f"{k}: {GoogleIntegrationClient._flatten(body[k])}" for k in ordered
            ]
            if parts:
                return "; ".join(parts)
        if isinstance(body, list) and body:
            return GoogleIntegrationClient._flatten(body)
        return f"Request failed with status {status_code}"

    @staticmethod
    def _is_account_error(status_code: int, body: dict | list | None) -> bool:
        """True if a 400 describes a Google account configuration fault."""
        if status_code != 400 or not isinstance(body, dict):
            return False
        if any(body.get(field) for field in _ACCOUNT_ERROR_FIELDS):
            return True
        detail = GoogleIntegrationClient._flatten(body.get("detail") or "").lower()
        return any(hint in detail for hint in _ACCOUNT_ERROR_HINTS)

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
        """
        Create a calendar event with a Google Meet link.

        Books on the Google account bound to this client's API key; the response reports
        it as ``google_account_email``. Raises ``GoogleIntegrationAccountError`` if that
        account is missing or unusable.
        """
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

    def check_event_held(
        self, event_id: int | str, *, raw: bool = False
    ) -> dict | None:
        """Check whether an event's Meet session was held (by numeric event id)."""
        return self.events.check_held(event_id, raw=raw)

    def check_event_held_by_code(
        self, meeting_code: str, *, raw: bool = False
    ) -> dict | None:
        """Check whether a Meet session was held, by meeting code (e.g. "abc-defg-hij")."""
        return self.events.check_held_by_code(meeting_code, raw=raw)

    def is_session_held(self, meeting_code: str, *, min_participants: int = 3) -> bool:
        """Return True only if the Meet session was held with more than 2 participants.

        Business rule: a session counts as "held" only when more than two people
        actually attended (default ``min_participants=3``). Anything else -- not held,
        held with 2 or fewer participants, no participant data, or event not found --
        returns False.

        Note that an unknown meeting code returns False rather than raising: the backend
        answers 404 for a code this API key cannot see, and this predicate is documented
        to treat "not found" as "not held". Account misconfiguration still raises, because
        that is a fault to fix rather than a negative answer.
        """
        try:
            event = self.events.check_held_by_code(meeting_code)
        except GoogleIntegrationNotFoundError:
            return False
        if not isinstance(event, dict):
            return False
        was_held = bool(event.get("was_held"))
        participant_count = event.get("participant_count") or 0
        return was_held and participant_count >= min_participants

    # --- service availability -----------------------------------------------------

    def health(self, *, raw: bool = False) -> dict | None:
        """
        Liveness: is the backend serving requests? Unauthenticated.

        Cheap and dependency-free; use it to tell "backend down" apart from
        "backend up but the Google integration is not configured" (see ``readiness``).
        """
        result = self._request("GET", "api/health/", require_auth=False, raw=raw)
        return result if isinstance(result, dict) else None

    def readiness(self, *, raw: bool = False) -> dict | None:
        """
        Readiness: per-service availability, including the Google integration.

        Unauthenticated. The backend answers 503 when a service is unhealthy, which is
        raised as ``GoogleIntegrationAPIError``; the parsed body is on ``.body``.
        Makes no outbound calls to Google, so it does not depend on Google's uptime.
        """
        result = self._request("GET", "api/readiness/", require_auth=False, raw=raw)
        return result if isinstance(result, dict) else None

    def google_integration_status(self) -> dict | None:
        """
        Return just the backend's ``google_integration`` readiness check, or None.

        Status values: ``healthy`` (bookable now), ``degraded`` (up but not configured or
        no bookable account), ``unhealthy`` (broken). ``details`` carries account and
        client counts.
        """
        try:
            payload = self.readiness()
        except GoogleIntegrationAPIError as exc:
            # 503 still carries a payload describing why; prefer it to raising.
            payload = exc.body if isinstance(exc.body, dict) else None
            if payload and isinstance(payload.get("data"), dict):
                payload = payload["data"]
        if not isinstance(payload, dict):
            return None
        services = payload.get("services")
        if not isinstance(services, dict):
            return None
        check = services.get("google_integration")
        return check if isinstance(check, dict) else None

    def is_google_integration_available(self) -> bool:
        """
        True if the backend can book on a Google account right now.

        False when the integration is unconfigured, has no bookable account, is broken,
        or the backend is unreachable. Intended as a pre-flight check so a caller can
        surface a clear message instead of failing on the first create.
        """
        try:
            check = self.google_integration_status()
        except Exception:
            return False
        return bool(check) and check.get("status") == "healthy"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GoogleIntegrationClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
