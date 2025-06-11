"""Wrapper around Tweepy for posting threads."""

from typing import List, Optional
import logging
import tweepy

from config import TwitterCredentials

logger = logging.getLogger(__name__)


def publish_thread(tweets: List[str], images: List[Optional[str]], creds: TwitterCredentials) -> None:
    """Publish a sequence of tweets as a thread."""
    auth = tweepy.OAuth1UserHandler(
        creds.api_key,
        creds.api_secret,
        creds.access_token,
        creds.access_secret,
    )
    api = tweepy.API(auth)

    previous_id: Optional[int] = None
    for txt, img in zip(tweets, images):
        media_ids = None
        if img:
            upload = api.media_upload(img)
            media_ids = [upload.media_id]

        status = api.update_status(
            status=txt,
            in_reply_to_status_id=previous_id,
            auto_populate_reply_metadata=bool(previous_id),
            media_ids=media_ids,
        )
        previous_id = status.id

    logger.info("Thread published successfully")
