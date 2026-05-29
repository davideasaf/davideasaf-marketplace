#!/usr/bin/env python3
"""
Setup OAuth credentials for nanobanana-image-gen.
Bypasses gcloud CLI by using direct OAuth flow.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Skill directory
SKILL_DIR = Path(__file__).parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"

def ensure_venv():
    """Ensure venv exists. Re-exec if needed."""
    import os
    if sys.prefix == str(VENV_DIR):
        return
    if not VENV_PYTHON.exists():
        print("Setting up virtual environment...")
        subprocess.run(["uv", "venv", str(VENV_DIR)], cwd=SKILL_DIR, check=True)
        subprocess.run(["uv", "pip", "install", "-e", str(SKILL_DIR)],
                      env={**os.environ, "VIRTUAL_ENV": str(VENV_DIR)},
                      check=True)
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

ensure_venv()

import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Google OAuth settings (same as gcloud CLI uses)
CLIENT_ID = "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"  # Public - same as gcloud
REDIRECT_URI = "http://localhost:8085"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/accounts.reauth",
]

ADC_PATH = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
# Optional expected account email (override via env). When empty, any Google
# account is accepted and no login_hint is sent.
EXPECTED_EMAIL = os.environ.get("NANOBANANA_ACCOUNT", "").strip()

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Authentication successful!</h1>
                <p>You can close this tab and return to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authentication failed")

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def authenticate():
    """Run OAuth flow and save credentials."""
    global auth_code

    # Build auth URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        "response_type=code&"
        f"scope={'+'.join(SCOPES)}&"
        "access_type=offline&"
        "prompt=consent"
        + (f"&login_hint={EXPECTED_EMAIL}" if EXPECTED_EMAIL else "")
    )

    print(f"Opening browser for authentication...")
    if EXPECTED_EMAIL:
        print(f"Please sign in with: {EXPECTED_EMAIL}")
    print()
    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(("localhost", 8085), OAuthHandler)
    server.handle_request()

    if not auth_code:
        print("ERROR: No authorization code received")
        sys.exit(1)

    # Exchange code for tokens
    print("Exchanging code for tokens...")
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }
    )

    if response.status_code != 200:
        print(f"ERROR: Token exchange failed: {response.text}")
        sys.exit(1)

    tokens = response.json()

    # Verify the email
    userinfo = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    ).json()

    email = userinfo.get("email")
    if EXPECTED_EMAIL and email != EXPECTED_EMAIL:
        print(f"ERROR: Wrong account! Got {email}, expected {EXPECTED_EMAIL}")
        sys.exit(1)

    # Save as ADC format
    adc_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
        "type": "authorized_user",
    }

    ADC_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADC_PATH.write_text(json.dumps(adc_data, indent=2))

    print(f"\n✓ Authenticated as: {email}")
    print(f"✓ Credentials saved to: {ADC_PATH}")


def main():
    print("=" * 50)
    print("Nanobanana Image Gen - OAuth Setup")
    print("=" * 50)
    print()
    if EXPECTED_EMAIL:
        print(f"This will authenticate with: {EXPECTED_EMAIL}")
        print()

    # Check current state
    if ADC_PATH.exists():
        try:
            from auth import get_current_adc_email
            current = get_current_adc_email()
        except (ImportError, AttributeError):
            current = None
        if current and EXPECTED_EMAIL and current == EXPECTED_EMAIL:
            print(f"✓ Already authenticated as {EXPECTED_EMAIL}")
            return
        elif current:
            print(f"Current credentials: {current}")
            if EXPECTED_EMAIL:
                print(f"Will replace with: {EXPECTED_EMAIL}")
            print()

    response = input("Continue? [Y/n]: ").strip().lower()
    if response and response != "y":
        print("Cancelled.")
        return

    print()
    authenticate()


if __name__ == "__main__":
    main()
