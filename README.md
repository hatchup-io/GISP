# GISP

Google Integration Service Proxy — a Python client for the Google-integration backend calendar events API. Authenticates with an API key; supports list, create, get, update, and delete for calendar events.

**The API key decides which Google calendar an event lands on.** The backend binds each API client to one Google account, so a key is effectively a handle to a calendar — there is no request field to choose one. Responses report the account used as `google_account_email`.

## Install

**From this repo (development):**

```bash
cd /path/to/GISP
pip install -e .
# or
uv pip install -e .
```

**In another project** — use one of the following from the other project’s environment:

-   **Local path (editable):** if GISP is on the same machine

    ```bash
    pip install -e /path/to/GISP
    uv pip install -e /path/to/GISP
    ```

-   **Local path (copy):** install as a normal package (no `-e`)

    ```bash
    pip install /path/to/GISP
    uv pip install /path/to/GISP
    ```

-   **From Git:** if GISP is in a Git repo (e.g. GitHub)

    ```bash
    pip install git+https://github.com/your-org/GISP.git
    pip install git+https://github.com/your-org/GISP.git@main
    uv pip install "gisp @ git+https://github.com/your-org/GISP.git"
    ```

-   **From PyPI (after publishing):**
    ```bash
    pip install gisp
    uv add gisp
    ```

Then in Python: `from google_integration_proxy import GoogleIntegrationClient`

## Base URL from environment

You can omit `base_url` and have it resolved from the environment:

-   **ENV** or **ENVIRONMENT** (e.g. `staging`, `production`, `local`):
    -   **staging** → `https://api.google-integration.service.staging.hatchup.capital`
    -   **production** → `https://api.google-integration.service.hatchup.capital`
    -   **local** (or unset) → use **GOOGLE_INTEGRATION_BASE_URL** (must be set for local)

```python
import os

os.environ["ENV"] = "staging"
client = GoogleIntegrationClient(api_key="your-api-key")  # uses staging URL

# Or pass base_url explicitly to ignore env
client = GoogleIntegrationClient("https://custom.example.com", api_key="...")
```

## Which Google account is used

Each API key maps to exactly one Google account in the backend:

```python
event = client.create_event("Standup", "2026-09-20T10:00:00Z", "2026-09-20T10:30:00Z")
event["google_account_email"]  # -> "bookings@example.com"
```

Consequences worth knowing:

-   **Events are scoped to the key that created them.** Listing with one key never returns another key's events, and fetching another key's event by id raises `GoogleIntegrationNotFoundError`.
-   **To book on several calendars, hold several keys** and choose the client per calendar. There is no per-request account override — sending `google_account_email` is ignored, since the backend treats it as read-only.
-   The account is **pinned at creation**, so an event keeps pointing at the calendar it lives on even if the API client is later re-bound to a different account.

```python
clients = {
    "eu": GoogleIntegrationClient(api_key=EU_KEY),
    "us": GoogleIntegrationClient(api_key=US_KEY),
}
clients["eu"].create_event("EU sync", start, end)  # books on the EU calendar
```

## Service availability

Check the backend can book before trying, so you can surface a clear message instead of failing on the first create. Both probes are unauthenticated and make **no** calls to Google, so they do not depend on Google's uptime.

```python
if not client.is_google_integration_available():
    check = client.google_integration_status()
    # status: "healthy" | "degraded" | "unhealthy"; details has account/client counts
    raise RuntimeError(
        f"cannot book: {check['message'] if check else 'backend unreachable'}"
    )

client.health()  # liveness: is the backend serving at all?
client.readiness()  # full per-service payload
```

`degraded` means the backend is up but cannot currently book — typically no Google account is connected, or no API client is bound to one. `unhealthy` means something is broken.

## Usage

```python
from google_integration_proxy import (
    GoogleIntegrationClient,
    GoogleIntegrationAPIError,
    GoogleIntegrationAuthError,
)

client = GoogleIntegrationClient(
    "https://your-google-integration-host.example.com",
    api_key="your-api-key",
)

# Option 1: use the events service
events = client.events.list(page=1, page_size=10)
event = client.events.create(
    "Team standup",
    "2025-03-01T10:00:00Z",
    "2025-03-01T10:30:00Z",
    description="Weekly sync",
    attendees=[
        {"email": "alice@example.com", "role": "required"},
        {"email": "bob@example.com", "role": "optional", "display_name": "Bob"},
    ],
)
one = client.events.get(event["id"])
client.events.update(event["id"], summary="Team standup (updated)", partial=True)
client.events.delete(event["id"])

# Option 2: use client methods (delegate to the service)
events = client.list_events(page=1, page_size=10)
event = client.create_event(
    "Team standup", "2025-03-01T10:00:00Z", "2025-03-01T10:30:00Z"
)
client.update_event(event["id"], summary="Updated", partial=True)
client.delete_event(event["id"])
```

Attendee `role` must be one of: `required`, `optional`, `moderator`.

## Check whether a Meet session was held

The Calendar API can't tell you if a scheduled Meet actually happened. These call the
backend's Meet check, which queries the Google Meet API, persists the result, and returns
the updated event (`was_held`, `participant_count`, `held_started_at`, `held_ended_at`).

```python
# By numeric event id:
event = client.check_event_held(event["id"])

# By Meet meeting code (e.g. from the join link meet.google.com/abc-defg-hij):
event = client.check_event_held_by_code("abc-defg-hij")
print(event["was_held"], event["participant_count"])

# Business rule: True only if the session was held with MORE THAN 2 participants.
if client.is_session_held("abc-defg-hij"):
    ...  # count the meeting as attended

# Adjust the threshold if needed (default 3 = "more than 2"):
client.is_session_held("abc-defg-hij", min_participants=2)
```

`is_session_held` returns `False` for: not held, held with 2 or fewer participants, no
participant data available, or no matching event found (including a meeting code that
belongs to another API key's account).

It still **raises** `GoogleIntegrationAccountError` if the backend cannot reach Google
at all — a broken binding or revoked token is a fault to fix, not a "not held" answer.

Note `check_event_held` takes the **numeric `id`**, not `meeting_code` or
`google_event_id`; passing either of those raises `GoogleIntegrationNotFoundError`.
Use `check_event_held_by_code` for a meeting code.

## Exceptions

All inherit from `GoogleIntegrationAPIError`, so existing `except GoogleIntegrationAPIError` handlers keep working.

| Exception | Raised on | What to do |
| --- | --- | --- |
| `GoogleIntegrationAuthError` | 401/403 | Invalid or inactive API key — check the key. |
| `GoogleIntegrationNotFoundError` | 404 | No such event, or it belongs to another key's account. |
| `GoogleIntegrationAccountError` | 400 (account faults) | Fix the backend: bind an account, re-enable it, or reconnect a revoked token. Retrying will not help. |
| `GoogleIntegrationAPIError` | anything else | Base error; carries `status_code` and parsed `body`. |

```python
from google_integration_proxy import GoogleIntegrationAccountError

try:
    client.create_event("Standup", start, end)
except GoogleIntegrationAccountError as exc:
    # e.g. "google_account: API client 'Acme' has no Google account bound. Set one in
    # admin: Google Integration -> Google Integration Clients -> Acme -> Google account."
    alert_ops(exc.message)
```

Error messages preserve the backend's wording, including DRF field-keyed validation errors
(`{"google_account": ["..."]}`), which earlier versions reduced to
`Request failed with status 400`.

## Development

-   Python 3.12+
-   `httpx` for HTTP. No Django dependency.

```bash
uv sync --all-groups
uv run pytest          # 30 tests, no network (httpx.MockTransport)
uv run ruff check .
uv run ruff format --check .
```

## Publishing to PyPI

1. **Create a PyPI account** at [pypi.org](https://pypi.org/account/register/) and (optionally) create an API token under Account settings → API tokens.

2. **Bump version** in `pyproject.toml` if needed (e.g. `version = "0.1.2"`).

3. **Build and publish** with UV (recommended):

    ```bash
    uv build
    uv publish
    ```

    When prompted, use your PyPI username and password, or set the token as the password. To use an API token non-interactively:

    ```bash
    uv publish --token pypi-YOUR_API_TOKEN
    ```

    Or with Twine (build then upload):

    ```bash
    pip install build twine
    python -m build
    twine upload dist/*
    ```

    For Test PyPI first: `uv publish --repository testpypi` or `twine upload --repository testpypi dist/*`.

4. **Install from PyPI**: `pip install gisp` or `uv add gisp`.
