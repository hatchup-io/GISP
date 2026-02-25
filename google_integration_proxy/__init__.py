"""Google Integration Service Proxy - client for Google-integration backend calendar events API."""

from __future__ import annotations

from google_integration_proxy.client import GoogleIntegrationClient
from google_integration_proxy.events import EventsService
from google_integration_proxy.exceptions import (
    GoogleIntegrationAPIError,
    GoogleIntegrationAuthError,
)

__all__ = [
    "GoogleIntegrationClient",
    "EventsService",
    "GoogleIntegrationAPIError",
    "GoogleIntegrationAuthError",
]
