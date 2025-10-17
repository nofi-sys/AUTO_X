import unittest
from unittest.mock import patch, MagicMock, call

from config import TwitterCredentials
from twitter_api import publish_thread


class TestPublishThread(unittest.TestCase):
    @patch("twitter_api.load_twitter_credentials")
    @patch("twitter_api.tweepy.API")
    def test_publish_text_only_thread(self, mock_api_class, mock_load_creds):
        """Verify that a simple text-only thread is published correctly."""
        # --- Mocks Setup ---
        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": 101}),
            MagicMock(data={"id": 102}),
        ]
        mock_api = mock_api_class.return_value

        # --- Call the function ---
        tweets = ["First tweet", "Second tweet"]
        images = [None, None]
        publish_thread(tweets, images, mock_client)

        # --- Assertions ---
        # Assert create_tweet was called correctly
        calls = [
            call(text="First tweet", in_reply_to_tweet_id=None, media_ids=None, user_auth=True),
            call(text="Second tweet", in_reply_to_tweet_id=101, media_ids=None, user_auth=True),
        ]
        mock_client.create_tweet.assert_has_calls(calls)
        self.assertEqual(mock_client.create_tweet.call_count, 2)

        # Assert media upload was NOT called
        mock_api.media_upload.assert_not_called()
        mock_load_creds.assert_not_called()

    @patch("twitter_api.load_twitter_credentials")
    @patch("twitter_api.tweepy.API")
    def test_publish_thread_with_images(self, mock_api_class, mock_load_creds):
        """Verify that a thread with images is published correctly."""
        # --- Mocks Setup ---
        mock_client = MagicMock()
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": 201}),
            MagicMock(data={"id": 202}),
        ]

        mock_api = mock_api_class.return_value
        mock_api.media_upload.return_value = MagicMock(media_id=999)

        # Mock credentials for media upload
        mock_creds = MagicMock()
        mock_creds.api_key = "key"
        mock_creds.api_secret = "secret"
        mock_creds.access_token = "token"
        mock_creds.access_secret = "secret"
        mock_load_creds.return_value = mock_creds

        # --- Call the function ---
        tweets = ["Tweet with image", "Just text"]
        images = ["/path/to/image.png", None]
        publish_thread(tweets, images, mock_client)

        # --- Assertions ---
        # Assert media_upload was called once with the correct filename
        mock_api.media_upload.assert_called_once_with(filename="/path/to/image.png")

        # Assert create_tweet was called correctly, with media_ids for the first one
        calls = [
            call(text="Tweet with image", in_reply_to_tweet_id=None, media_ids=[999], user_auth=True),
            call(text="Just text", in_reply_to_tweet_id=201, media_ids=None, user_auth=True),
        ]
        mock_client.create_tweet.assert_has_calls(calls)
        self.assertEqual(mock_client.create_tweet.call_count, 2)