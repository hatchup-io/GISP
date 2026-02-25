"""Typed structures for calendar event request/response (optional, for IDE/type checking)."""

from __future__ import annotations

from typing import TypedDict


class AttendeePayload(TypedDict, total=False):
    """Payload for creating/updating an attendee. role: required | optional | moderator."""

    email: str
    role: str
    display_name: str


class CalendarEventPayload(TypedDict, total=False):
    """Payload for creating/updating a calendar event. start/end are ISO 8601 strings."""

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
    summary: str
    description: str
    start: str
    end: str
    time_zone: str
    meet_link: str
    is_synced: bool
    attendees: list[AttendeeResponse]
    created_at: str
    updated_at: str
