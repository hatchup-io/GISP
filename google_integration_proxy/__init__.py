"""Google Integration Service Proxy - client for Google-integration backend calendar events API."""

from __future__ import annotations

from google_integration_proxy.client import (
    GoogleIntegrationClient,
    get_base_url_from_env,
    LOCAL_BASE_URL_ENV_VAR,
    PRODUCTION_BASE_URL,
    STAGING_BASE_URL,
)
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
    "get_base_url_from_env",
    "LOCAL_BASE_URL_ENV_VAR",
    "PRODUCTION_BASE_URL",
    "STAGING_BASE_URL",
]
