# GISP

Google Integration Service Proxy — a Python client for the Google-integration backend calendar events API. Authenticates with an API key; supports list, create, get, update, and delete for calendar events.

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

## Usage

```python
from google_integration_proxy import GoogleIntegrationClient, GoogleIntegrationAPIError, GoogleIntegrationAuthError

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
event = client.create_event("Team standup", "2025-03-01T10:00:00Z", "2025-03-01T10:30:00Z")
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
participant data available, or no matching event found.

## Exceptions

-   `GoogleIntegrationAPIError`: base API error (status_code, body).
-   `GoogleIntegrationAuthError`: 401/403 (invalid or inactive API key).

## Development

-   Python 3.12+
-   `httpx` for HTTP. No Django dependency.

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
