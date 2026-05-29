#!/usr/bin/env python3
"""
Authentication utilities for nanobanana-image-gen.

Auth resolution order:
  1. If GEMINI_API_KEY or GOOGLE_API_KEY is set, the google-genai SDK uses it
     directly and no gcloud setup is needed.
  2. Otherwise, gcloud OAuth credentials are used via a named gcloud
     configuration. Configure with environment variables:
       NANOBANANA_GCLOUD_CONFIG  gcloud configuration name (default: "default")
       NANOBANANA_ACCOUNT        (optional) expected account email; when set,
                                 the config's account is verified to match it.
"""

import os
import subprocess
import sys

# gcloud configuration to use for this skill (override via env)
GCLOUD_CONFIG = os.environ.get("NANOBANANA_GCLOUD_CONFIG", "default")
# Optional expected account email; when empty, account matching is skipped.
EXPECTED_EMAIL = os.environ.get("NANOBANANA_ACCOUNT", "").strip()


def setup_environment():
    """Point gcloud at the configured configuration."""
    os.environ["CLOUDSDK_ACTIVE_CONFIG_NAME"] = GCLOUD_CONFIG


def get_config_account() -> str | None:
    """Get the account associated with the configured gcloud config."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get", "account", f"--configuration={GCLOUD_CONFIG}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def verify_config_exists() -> bool:
    """Verify the configured gcloud configuration exists."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "configurations", "list", "--format=value(name)"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            configs = result.stdout.strip().split("\n")
            return GCLOUD_CONFIG in configs
    except Exception:
        pass
    return False


def verify_account() -> bool:
    """
    Verify the configured gcloud configuration is set up correctly.

    Returns:
        True if the config exists and (when NANOBANANA_ACCOUNT is set) its
        account matches the expected email.
    """
    if not verify_config_exists():
        print(f"⚠️  gcloud configuration '{GCLOUD_CONFIG}' not found.")
        print(f"\nCreate it with:")
        print(f"  gcloud config configurations create {GCLOUD_CONFIG}")
        if EXPECTED_EMAIL:
            print(f"  gcloud config set account {EXPECTED_EMAIL} --configuration={GCLOUD_CONFIG}")
            print(f"  gcloud auth login {EXPECTED_EMAIL} --configuration={GCLOUD_CONFIG}")
        else:
            print(f"  gcloud auth login --configuration={GCLOUD_CONFIG}")
        return False

    account = get_config_account()
    if not account:
        print(f"⚠️  Config '{GCLOUD_CONFIG}' has no account set.")
        print(f"\nFix with:")
        print(f"  gcloud auth login --configuration={GCLOUD_CONFIG}")
        return False

    if EXPECTED_EMAIL and account != EXPECTED_EMAIL:
        print(f"⚠️  Config '{GCLOUD_CONFIG}' has account: {account}")
        print(f"   Expected (NANOBANANA_ACCOUNT): {EXPECTED_EMAIL}")
        print(f"\nFix with:")
        print(f"  gcloud auth login {EXPECTED_EMAIL} --configuration={GCLOUD_CONFIG}")
        return False

    return True


def require_correct_account():
    """Set up environment and exit if config is wrong.

    If GEMINI_API_KEY or GOOGLE_API_KEY is set, skip gcloud checks entirely —
    the google-genai SDK will use the API key directly.
    """
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return  # API key auth — no gcloud needed
    setup_environment()
    if not verify_account():
        sys.exit(1)


if __name__ == "__main__":
    # Quick check script
    if verify_config_exists():
        account = get_config_account()
        if account:
            ok = (not EXPECTED_EMAIL) or (account == EXPECTED_EMAIL)
            status = "✓" if ok else "✗"
            print(f"{status} Config '{GCLOUD_CONFIG}' account: {account}")
            if not ok:
                print(f"  Expected (NANOBANANA_ACCOUNT): {EXPECTED_EMAIL}")
                sys.exit(1)
            print(f"  Environment will use: CLOUDSDK_ACTIVE_CONFIG_NAME={GCLOUD_CONFIG}")
        else:
            print(f"✗ Config '{GCLOUD_CONFIG}' has no account set")
            sys.exit(1)
    else:
        print(f"✗ gcloud configuration '{GCLOUD_CONFIG}' not found")
        print(f"  Create with: gcloud config configurations create {GCLOUD_CONFIG}")
        sys.exit(1)
