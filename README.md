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

## Exceptions

-   `GoogleIntegrationAPIError`: base API error (status_code, body).
-   `GoogleIntegrationAuthError`: 401/403 (invalid or inactive API key).

## Development

-   Python 3.12+
-   `httpx` for HTTP. No Django dependency.
