"""Wrapper around Tweepy for posting threads."""

from typing import List, Optional
import logging
import tweepy

from config import TwitterCredentials

logger = logging.getLogger(__name__)


def publish_thread(tweets: List[str], images: List[Optional[str]], creds: TwitterCredentials) -> None:
    """Publish a sequence of tweets as a thread using Twitter API v2."""
    # API v1.1 client is still needed for media uploads
    auth = tweepy.OAuth1UserHandler(
        creds.api_key,
        creds.api_secret,
        creds.access_token,
        creds.access_secret,
    )
    api_v1 = tweepy.API(auth)

    # API v2 client for creating tweets
    client_v2 = tweepy.Client(
        consumer_key=creds.api_key,
        consumer_secret=creds.api_secret,
        access_token=creds.access_token,
        access_token_secret=creds.access_secret,
    )

    previous_id: Optional[int] = None
    for txt, img in zip(tweets, images):
        media_ids = None
        if img:
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
