"""Typed structures for calendar event request/response (optional, for IDE/type checking)."""

from __future__ import annotations

from typing import TypedDict


class AttendeePayload(TypedDict, total=False):
    """Payload for creating/updating an attendee. role: required | optional | moderator."""

    email: str
    role: str
    display_name: str


class CalendarEventPayload(TypedDict, total=False):
    """
    Payload for creating/updating a calendar event. start/end are ISO 8601 strings.

    There is deliberately no account field: the API key selects the Google account, and
    sending ``google_account_email`` has no effect because the backend treats it as
    read-only.
    """

    summary: str
    description: str
    start: str
    end: str
    time_zone: str
    attendees: list[AttendeePayload]


class AttendeeResponse(TypedDict, total=False):
    """Attendee as returned by the API."""

    id: int
    email: str
    role: str
    display_name: str
    created_at: str


class CalendarEventResponse(TypedDict, total=False):
    """Calendar event as returned by the API."""

    id: int
    google_event_id: str
    # Google account this event was booked on. Read-only: determined by the API key used,
    # not settable on create or update. Pinned at creation, so it keeps identifying the
    # calendar the event lives on even if the API client is later re-bound.
    google_account_email: str
    summary: str
    description: str
    start: str
    end: str
    time_zone: str
    meet_link: str
    meeting_code: str
    is_synced: bool
    # Populated by check-held: whether the Meet session was actually held.
    was_held: bool
    conference_checked_at: str
    held_started_at: str
    held_ended_at: str
    participant_count: int
    attendees: list[AttendeeResponse]
    created_at: str
    updated_at: str


class ServiceCheck(TypedDict, total=False):
    """One service entry from the readiness payload."""

    name: str
    # healthy | degraded | unhealthy | skipped | disabled
    status: str
    message: str
    latency_ms: float
    details: dict


class ReadinessResponse(TypedDict, total=False):
    """Readiness payload. HTTP status is 503 when any service is unhealthy."""

    status: str
    environment: str
    timestamp: str
    services: dict[str, ServiceCheck]


class HealthResponse(TypedDict, total=False):
    """Liveness payload."""

    status: str
    environment: str
    timestamp: str
