"""Exceptions raised by the Google Integration proxy client."""

from __future__ import annotations


class GoogleIntegrationAPIError(Exception):
    """Base exception for API errors from the Google-integration backend."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        body: dict | list | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class GoogleIntegrationAuthError(GoogleIntegrationAPIError):
    """Raised on 401/403 (invalid or inactive API key)."""

    pass
