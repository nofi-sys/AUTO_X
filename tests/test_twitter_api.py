import unittest
from unittest.mock import patch, MagicMock, call

from config import TwitterCredentials
from twitter_api import publish_thread


class TestPublishThread(unittest.TestCase):
    def setUp(self):
        """Prepare a dummy credentials object for all tests."""
        self.creds = TwitterCredentials("key", "secret", "token", "token_secret")

    @patch("twitter_api.tweepy.Client")
    @patch("twitter_api.tweepy.API")
    def test_publish_text_only_thread(self, mock_api_class, mock_client_class):
        """Verify that a simple text-only thread is published correctly."""
        # --- Mocks Setup ---
        mock_client = mock_client_class.return_value
        # Simulate the response from create_tweet, which contains the new tweet's ID
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": 101}),
            MagicMock(data={"id": 102}),
        ]
        mock_api = mock_api_class.return_value

        # --- Call the function ---
        tweets = ["First tweet", "Second tweet"]
        images = [None, None]
        publish_thread(tweets, images, self.creds)

        # --- Assertions ---
        # Assert client was initialized
        mock_client_class.assert_called_once_with(
            consumer_key="key",
            consumer_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
        )

        # Assert create_tweet was called correctly
        calls = [
            call(text="First tweet", in_reply_to_tweet_id=None, media_ids=None),
            call(text="Second tweet", in_reply_to_tweet_id=101, media_ids=None),
        ]
        mock_client.create_tweet.assert_has_calls(calls)
        self.assertEqual(mock_client.create_tweet.call_count, 2)

        # Assert media upload was NOT called
        mock_api.media_upload.assert_not_called()

    @patch("twitter_api.tweepy.Client")
    @patch("twitter_api.tweepy.API")
    def test_publish_thread_with_images(self, mock_api_class, mock_client_class):
        """Verify that a thread with images is published correctly."""
        # --- Mocks Setup ---
        mock_client = mock_client_class.return_value
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": 201}),
            MagicMock(data={"id": 202}),
        ]

        mock_api = mock_api_class.return_value
        # Simulate the response from media_upload
        mock_api.media_upload.return_value = MagicMock(media_id=999)

        # --- Call the function ---
        tweets = ["Tweet with image", "Just text"]
        images = ["/path/to/image.png", None]
        publish_thread(tweets, images, self.creds)

        # --- Assertions ---
        # Assert media_upload was called once with the correct filename
        mock_api.media_upload.assert_called_once_with(filename="/path/to/image.png")

        # Assert create_tweet was called correctly, with media_ids for the first one
        calls = [
            call(text="Tweet with image", in_reply_to_tweet_id=None, media_ids=[999]),
            call(text="Just text", in_reply_to_tweet_id=201, media_ids=None),
        ]
        mock_client.create_tweet.assert_has_calls(calls)
        self.assertEqual(mock_client.create_tweet.call_count, 2)