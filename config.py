"""Credential loading utilities."""

from dataclasses import dataclass
import os
import json
from typing import Optional, Dict, Any

from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

# --- Google Drive Workspace ---
# Override `GOOGLE_DRIVE_WORKSPACE_ID` in your .env file to point the app to a different Drive folder.
# If you prefer to hardcode a new default, edit `DEFAULT_WORKSPACE_FOLDER_ID` below.
DEFAULT_WORKSPACE_FOLDER_ID = "1YRa4WJFr53mUP4I4R1WECznRjAEOzFm6"

OAUTH2_TOKEN_FILE = "oauth2_token.json"


# --- OAuth 1.0a Credentials (for media uploads) ---
@dataclass
class TwitterCredentials:
    """Container for Twitter API v1.1 credentials."""

    api_key: str
    api_secret: str
    access_token: str
    access_secret: str


def load_twitter_credentials() -> TwitterCredentials:
    """Load Twitter v1.1 credentials from environment variables."""
    return TwitterCredentials(
        api_key=os.getenv("TWITTER_API_KEY", ""),
        api_secret=os.getenv("TWITTER_API_SECRET", ""),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
        access_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
    )


# --- OAuth 2.0 Credentials (for main API calls) ---
@dataclass
class TwitterOAuth2Credentials:
    """Container for Twitter API OAuth 2.0 client credentials."""

    client_id: str
    client_secret: str


def load_twitter_oauth2_credentials() -> TwitterOAuth2Credentials:
    """Load Twitter OAuth 2.0 client credentials from environment variables."""
    return TwitterOAuth2Credentials(
        client_id=os.getenv("TWITTER_CLIENT_ID", ""),
        client_secret=os.getenv("TWITTER_CLIENT_SECRET", ""),
    )


def load_google_drive_workspace_id() -> str:
    """
    Return the Google Drive folder ID where the app stores its threads.

    Update `GOOGLE_DRIVE_WORKSPACE_ID` in the .env file or edit `DEFAULT_WORKSPACE_FOLDER_ID`
    in config.py to change this location in the future.
    """
    folder_id = os.getenv("GOOGLE_DRIVE_WORKSPACE_ID")
    if folder_id and folder_id.strip():
        return folder_id.strip()
    return DEFAULT_WORKSPACE_FOLDER_ID


def save_oauth2_token(token: Dict[str, Any]) -> None:
    """Save the OAuth 2.0 token dictionary to a file."""
    try:
        with open(OAUTH2_TOKEN_FILE, "w") as f:
            json.dump(token, f, indent=2)
    except IOError as e:
        print(f"Error saving token: {e}")


def load_oauth2_token() -> Optional[Dict[str, Any]]:
    """Load the OAuth 2.0 token dictionary from a file."""
    if not os.path.exists(OAUTH2_TOKEN_FILE):
        return None
    try:
        with open(OAUTH2_TOKEN_FILE, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading token: {e}")
        return None


def load_openai_key() -> str:
    """Load the OpenAI API key from environment variables."""
    return os.getenv("OPENAI_API_KEY", "")
