"""Wrapper around Tweepy for posting threads."""

from typing import List, Optional
import logging
import tweepy

from config import load_twitter_credentials

logger = logging.getLogger(__name__)


def publish_thread(tweets: List[str], images: List[Optional[str]], client_v2: tweepy.Client) -> None:
    """
    Publish a sequence of tweets as a thread using an authenticated API v2 client.

    Media uploads still require an API v1.1 client, which is created on-the-fly
    using credentials from the .env file.
    """
    api_v1 = None
    # If there are images to upload, we need to set up the v1.1 client
    if any(img for img in images):
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

    previous_id: Optional[int] = None
    for txt, img in zip(tweets, images):
        media_ids = None
        if img:
            if not api_v1:
                # This case should be prevented by the check above, but as a safeguard:
                raise RuntimeError("Cannot upload media without a valid API v1.1 client.")
            # The v1.1 endpoint is the recommended way to upload media for v2
            upload = api_v1.media_upload(filename=img)
            media_ids = [upload.media_id]

        response = client_v2.create_tweet(
            text=txt,
            in_reply_to_tweet_id=previous_id,
            media_ids=media_ids,
        )
        # The response contains a data object with the new tweet's details
        previous_id = response.data["id"]

    logger.info("Thread published successfully")