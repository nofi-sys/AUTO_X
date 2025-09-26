import json
import unittest
from unittest.mock import patch, MagicMock

from ai_splitter import split_thread_with_ai, AI_MODEL, SYSTEM_PROMPT


class TestAiSplitter(unittest.TestCase):
    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_with_ai_success(self, mock_openai_class, mock_load_key):
        """Test the happy path where the AI returns a valid thread."""
        # --- Mocks Setup ---
        mock_client = mock_openai_class.return_value
        # Simulate the response from the chat completion
        expected_thread = ["Tweet 1/2", "Tweet 2/2"]
        response_content = json.dumps({"thread": expected_thread})
        mock_response = MagicMock()
        mock_response.choices[0].message.content = response_content
        mock_client.chat.completions.create.return_value = mock_response

        # --- Call the function ---
        text_to_split = "This is a long text to split."
        result = split_thread_with_ai(text_to_split)

        # --- Assertions ---
        self.assertEqual(result, expected_thread)
        mock_openai_class.assert_called_once_with(api_key="fake_api_key")
        mock_client.chat.completions.create.assert_called_once_with(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text_to_split},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

    @patch("ai_splitter.load_openai_key", return_value="")
    def test_split_thread_no_api_key(self, mock_load_key):
        """Test that a ValueError is raised if the API key is missing."""
        with self.assertRaisesRegex(ValueError, "OpenAI API key not found"):
            split_thread_with_ai("Some text")

    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_invalid_json(self, mock_openai_class, mock_load_key):
        """Test that a RuntimeError is raised if the AI returns invalid JSON."""
        # --- Mocks Setup ---
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is not JSON"
        mock_client.chat.completions.create.return_value = mock_response

        # --- Assertions ---
        with self.assertRaisesRegex(RuntimeError, "The AI returned an invalid JSON format."):
            split_thread_with_ai("Some text")

    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_malformed_json_structure(self, mock_openai_class, mock_load_key):
        """Test that a RuntimeError is raised if the JSON is missing the 'thread' key."""
        # --- Mocks Setup ---
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        # Valid JSON, but wrong structure
        mock_response.choices[0].message.content = json.dumps({"tweets": ["Tweet 1"]})
        mock_client.chat.completions.create.return_value = mock_response

        # --- Assertions ---
        with self.assertRaisesRegex(RuntimeError, "AI response is not a valid JSON array of strings."):
            split_thread_with_ai("Some text")