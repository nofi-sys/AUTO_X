"""Wrapper around Tweepy for posting threads."""

from typing import Callable, List, Optional
import logging
import time
import tweepy
from dataclasses import dataclass
from datetime import datetime, timezone

from config import load_twitter_credentials

logger = logging.getLogger(__name__)


@dataclass
class RateLimitStatus:
    """Represents the status of a Twitter API rate limit."""
    endpoint: str
    limit: int
    remaining: int
    reset_time: datetime

    def __str__(self):
        reset_str = self.reset_time.strftime('%H:%M:%S')
        return (
            f"Endpoint: {self.endpoint}\n"
            f"Limit: {self.limit} requests\n"
            f"Remaining: {self.remaining}\n"
            f"Resets at: {reset_str}"
        )


class ThreadPublishPartialError(RuntimeError):
    """Raised when the thread stops part-way through."""

    def __init__(
        self,
        message: str,
        *,
        next_index: int,
        last_tweet_id: Optional[int],
        posted_ids: List[Optional[int]],
        wait_seconds: Optional[int] = None,
        original: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.next_index = next_index
        self.last_tweet_id = last_tweet_id
        self.posted_ids = posted_ids
        self.wait_seconds = wait_seconds
        self.original = original


class RateLimitError(ThreadPublishPartialError):
    """Specialised error for 429 responses."""


def get_rate_limit_status(client_v2: tweepy.Client) -> Optional[RateLimitStatus]:
    """
    Fetches the current rate limit status for the tweet creation endpoint.

    This function makes a lightweight request to the 'users/me' endpoint to get
    the rate limit headers without consuming a request from the tweet creation quota.

    Args:
        client_v2: An authenticated Tweepy v2 client.

    Returns:
        A RateLimitStatus object if the headers are found, otherwise None.
    """
    try:
        # This is a lightweight call to get headers
        client_v2.get_me(user_auth=True)
        headers = client_v2.last_response.headers

        if not headers:
            logger.warning("Could not retrieve rate limit headers.")
            return None

        # Headers for the tweet creation endpoint
        # X-Rate-Limit-Limit: The rate limit ceiling for that endpoint.
        # X-Rate-Limit-Remaining: The number of requests left for the 15-minute window.
        # X-Rate-Limit-Reset: The time in UTC epoch seconds when the rate limit window resets.
        limit = int(headers.get("x-rate-limit-limit", 0))
        remaining = int(headers.get("x-rate-limit-remaining", 0))
        reset_timestamp = int(headers.get("x-rate-limit-reset", 0))
        reset_time = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)

        return RateLimitStatus(
            endpoint="/2/tweets",
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
        )
    except tweepy.errors.TweepyException as e:
        logger.error("Failed to fetch rate limit status: %s", e)
        return None


def _compute_wait_seconds(exc: tweepy.errors.TooManyRequests) -> Optional[int]:
    headers = getattr(exc, "response", None)
    if not headers or not getattr(headers, "headers", None):
        return None
    header_map = headers.headers
    retry_after = header_map.get("retry-after")
    if retry_after:
        try:
            retry_value = int(float(retry_after))
            return max(retry_value, 1)
        except (TypeError, ValueError):
            pass
    reset = header_map.get("x-rate-limit-reset")
    if reset:
        try:
            reset_ts = int(reset)
            wait_seconds = reset_ts - int(time.time())
            return max(wait_seconds, 1)
        except (TypeError, ValueError):
            return None
    return None


def publish_thread(
    tweets: List[str],
    images: List[Optional[str]],
    client_v2: tweepy.Client,
    *,
    start_index: int = 0,
    initial_reply_id: Optional[int] = None,
    delay_seconds: float = 2.0,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> List[Optional[int]]:
    """
    Publish a sequence of tweets as a thread using an authenticated API v2 client.

    Args:
        tweets: The ordered list of tweet texts.
        images: Optional list of media paths aligned with ``tweets``.
        client_v2: Tweepy v2 client with OAuth 2.0 or OAuth 1.0a user context.
        start_index: Tweet index to resume from (defaults to 0).
        initial_reply_id: Parent tweet ID when resuming a partial thread.
        delay_seconds: Seconds to wait between tweets to avoid rate limits.
        progress_callback: Optional callable invoked with (index, tweet_id) after each success.

    Returns:
        A list containing the tweet IDs for the indices that were posted in this run.

    Raises:
        RateLimitError: When Twitter returns HTTP 429.
        ThreadPublishPartialError: When posting stops mid-thread for other reasons.
    """
    total = len(tweets)
    if total == 0:
        return []

    posted_ids: List[Optional[int]] = [None] * total

    delay_seconds = max(delay_seconds, 0.0)

    api_v1 = None
    remaining_images = images[start_index:] if start_index < len(images) else []
    if any(img for img in remaining_images):
        creds_v1 = load_twitter_credentials()
        if not all([creds_v1.api_key, creds_v1.api_secret, creds_v1.access_token, creds_v1.access_secret]):
            raise ValueError(
                "OAuth 1.0a credentials (API Key/Secret, Access Token/Secret) are required "
                "for media uploads, but are not configured in the .env file."
            )
        auth_v1 = tweepy.OAuth1UserHandler(
            creds_v1.api_key,
            creds_v1.api_secret,
            creds_v1.access_token,
            creds_v1.access_secret,
        )
        api_v1 = tweepy.API(auth_v1)

    logger.debug(
        "Publishing thread using OAuth 2.0 for tweets and OAuth 1.0a for media."
    )

    previous_id: Optional[int] = initial_reply_id
    last_success_index = start_index - 1

    for idx in range(start_index, total):
        txt = tweets[idx]
        img = images[idx] if idx < len(images) else None

        media_ids = None
        if img:
            if not api_v1:
                raise RuntimeError("Cannot upload media without a valid API v1.1 client.")
            try:
                upload = api_v1.media_upload(filename=img)
            except tweepy.errors.Forbidden as exc:
                api_messages = getattr(exc, "api_messages", None) or []
                error_text = " ".join(api_messages) if api_messages else str(exc)
                raise PermissionError(
                    "Twitter rejected the media upload. Ensure your OAuth 1.0a credentials have Read & Write "
                    "permissions enabled and regenerate the Access Token & Secret in the developer portal. "
                    f"Twitter response: {error_text}"
                ) from exc
            media_ids = [upload.media_id]

        try:
            # When using a client with both OAuth 1.0a and OAuth 2.0 credentials,
            # we must specify `user_auth=True` to use the v1.1 endpoint for the request.
            # This is necessary for media uploads to work correctly.
            response = client_v2.create_tweet(
                text=txt,
                in_reply_to_tweet_id=previous_id,
                media_ids=media_ids,
                user_auth=True,
            )
        except tweepy.errors.Forbidden as exc:
            api_messages = getattr(exc, "api_messages", None) or []
            error_text = " ".join(api_messages) if api_messages else str(exc)
            if "oauth1" in error_text.lower():
                raise PermissionError(
                    "Twitter rejected the request because the OAuth 1.0a credentials in the .env file "
                    "do not have Read & Write permissions. Enable OAuth 1.0a with write access in the "
                    "Twitter developer portal, regenerate the Access Token & Secret, and update the .env."
                ) from exc
            if "duplicate content" in error_text.lower():
                snippet = (txt[:75] + "...") if len(txt) > 75 else txt
                raise ValueError(
                    "Twitter rejected one of the tweets because it matches content that was already posted. "
                    "Edit the tweet to make it unique and try again.\n\n"
                    f"Tweet snippet: \"{snippet}\""
                ) from exc
            raise
        except tweepy.errors.TooManyRequests as exc:
            wait_seconds = _compute_wait_seconds(exc)
            logger.warning(
                "Hit rate limit after posting %d/%d tweets. Suggested wait: %s seconds.",
                last_success_index + 1,
                total,
                wait_seconds if wait_seconds is not None else "unknown",
            )
            raise RateLimitError(
                "Twitter rate limited the thread publishing.",
                next_index=idx,
                last_tweet_id=previous_id,
                posted_ids=posted_ids,
                wait_seconds=wait_seconds,
                original=exc,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error while posting tweet %d", idx + 1)
            raise ThreadPublishPartialError(
                "Twitter rejected one of the tweets before the thread finished.",
                next_index=idx,
                last_tweet_id=previous_id,
                posted_ids=posted_ids,
                original=exc,
            ) from exc

        tweet_id = response.data["id"]
        previous_id = tweet_id
        posted_ids[idx] = tweet_id
        last_success_index = idx

        if progress_callback:
            try:
                progress_callback(idx, tweet_id)
            except Exception:  # pragma: no cover - callbacks should not break publishing
                logger.exception("Progress callback raised an error for tweet %d", idx + 1)

        if delay_seconds and idx < total - 1:
            time.sleep(delay_seconds)

    logger.info("Thread published successfully")
    return posted_ids
