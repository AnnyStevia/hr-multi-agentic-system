"""One-time local helper: obtain a Google Meet organizer refresh token.

Never writes secrets into the repository. Paste the printed refresh token into
backend/.env as GOOGLE_MEET_REFRESH_TOKEN (file is gitignored).

Usage (from backend/):

  .\\.venv\\Scripts\\python.exe scripts/obtain_google_meet_refresh_token.py

Or with client JSON path:

  .\\.venv\\Scripts\\python.exe scripts/obtain_google_meet_refresh_token.py path/to/client_secret.json

Requires google-auth-oauthlib (and google-auth / google-api-python-client already
used by the Meet provider).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _load_client_config(path: str | None) -> tuple[str, str]:
    env_id = (os.environ.get("GOOGLE_MEET_CLIENT_ID") or "").strip()
    env_secret = (os.environ.get("GOOGLE_MEET_CLIENT_SECRET") or "").strip()
    if env_id and env_secret and not path:
        return env_id, env_secret

    if not path:
        path = input(
            "Path to OAuth Desktop client JSON (downloaded from Google Cloud Console): "
        ).strip().strip('"')
    if not path or not os.path.isfile(path):
        raise SystemExit(f"Client JSON not found: {path!r}")

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    # Desktop clients use "installed"; web clients use "web".
    block = data.get("installed") or data.get("web")
    if not isinstance(block, dict):
        raise SystemExit("JSON must contain 'installed' (Desktop) or 'web' client block")

    client_id = (block.get("client_id") or "").strip()
    client_secret = (block.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise SystemExit("client_id / client_secret missing from JSON")
    return client_id, client_secret


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Obtain a Google Calendar refresh token for Meet provisioning."
    )
    parser.add_argument(
        "client_secret_json",
        nargs="?",
        default=None,
        help="Optional path to OAuth client JSON from Google Cloud Console",
    )
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Missing dependency: pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        return 1

    client_id, client_secret = _load_client_config(args.client_secret_json)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print()
    print("Opening browser for Google consent (scope: calendar.events only).")
    print("Sign in as the ORGANIZER account that will create Meet events.")
    print("Use a Desktop OAuth client; redirect URI http://localhost is used locally.")
    print()

    flow = InstalledAppFlow.from_client_config(client_config, scopes=[SCOPE])
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    refresh = getattr(credentials, "refresh_token", None)
    if not refresh:
        print(
            "No refresh_token returned. Revoke prior grants for this client at "
            "https://myaccount.google.com/permissions and re-run with prompt=consent.",
            file=sys.stderr,
        )
        return 1

    print()
    print("--- copy into backend/.env (do not commit) ---")
    print(f"GOOGLE_MEET_CLIENT_ID={client_id}")
    print("GOOGLE_MEET_CLIENT_SECRET=<your client secret>")
    print(f"GOOGLE_MEET_REFRESH_TOKEN={refresh}")
    print("MEETING_PROVIDER=google")
    print("GOOGLE_MEET_CALENDAR_ID=primary")
    print("--- end ---")
    print()
    print("Refresh token printed once above. Paste into backend/.env and keep it private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
