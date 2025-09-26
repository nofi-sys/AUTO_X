"""Credential loading utilities."""

from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()


@dataclass
class TwitterCredentials:
    """Container for Twitter API credentials."""

    api_key: str
    api_secret: str
    access_token: str
    access_secret: str


def load_twitter_credentials() -> TwitterCredentials:
    """Load Twitter credentials from environment variables."""
    return TwitterCredentials(
        api_key=os.getenv("TWITTER_API_KEY", ""),
        api_secret=os.getenv("TWITTER_API_SECRET", ""),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
        access_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
    )


def load_openai_key() -> str:
    """Load the OpenAI API key from environment variables."""
    return os.getenv("OPENAI_API_KEY", "")