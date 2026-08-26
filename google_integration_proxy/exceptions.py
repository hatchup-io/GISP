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


class GoogleIntegrationNotFoundError(GoogleIntegrationAPIError):
    """
    Raised on 404 (no such event, or an event belonging to another API client).

    Events are scoped to the API key that created them, so requesting an event booked by a
    different key is indistinguishable from one that does not exist.
    """

    pass


class GoogleIntegrationAccountError(GoogleIntegrationAPIError):
    """
    Raised when the backend cannot book because of a Google account problem.

    These are configuration faults on the integration side, not bad input, and retrying
    the same request will not help. Typical causes:

    - the API key's client has no Google account bound
    - the bound account is disabled or has no stored refresh token
    - Google rejected the account's refresh token (revoked or expired), so the
      account must be reconnected

    Which Google account is used is determined by the API key, so resolving these means
    fixing the binding or reconnecting the account in the backend admin - not changing
    the request.
    """

    pass
