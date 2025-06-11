"""Credential loading utilities."""

from dataclasses import dataclass
import os

@dataclass
class TwitterCredentials:
    """Container for Twitter API credentials."""

    api_key: str
    api_secret: str
    access_token: str
    access_secret: str


def load_credentials() -> TwitterCredentials:
    """Load Twitter credentials from environment variables."""
    return TwitterCredentials(
        api_key=os.getenv("TWITTER_API_KEY", ""),
        api_secret=os.getenv("TWITTER_API_SECRET", ""),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
        access_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
    )
