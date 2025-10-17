import json
import unittest
from unittest.mock import patch, MagicMock

from ai_splitter import split_thread_with_ai, AI_MODEL, SYSTEM_PROMPT


class TestAiSplitter(unittest.TestCase):
    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_with_ai_success(self, mock_openai_class, mock_load_key):
        """Test the happy path where the AI returns a valid list of threads."""
        # --- Mocks Setup ---
        mock_client = mock_openai_class.return_value
        expected_threads = [["Tweet 1/2", "Tweet 2/2"], ["Alt Tweet 1/1"]]
        response_content = json.dumps({"threads": expected_threads})
        mock_response = MagicMock()
        mock_response.choices[0].message.content = response_content
        mock_client.chat.completions.create.return_value = mock_response

        # --- Call the function ---
        text_to_split = "This is a long text to split."
        num_versions = 2
        result = split_thread_with_ai(
            text_to_split,
            model="gpt-4o-mini",
            language="English",
            extra_instructions="",
            num_versions=num_versions,
        )

        # --- Assertions ---
        self.assertEqual(result, expected_threads)
        mock_openai_class.assert_called_once_with(api_key="fake_api_key")
        expected_user_prompt = (
            f"Please generate {num_versions} different and distinct thread versions in English "
            f"for the following text. Each version should explore a different angle or aspect of the text.\n\n"
            f'Original Text:\n"""\n{text_to_split}\n"""\n'
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": expected_user_prompt},
            ],
            response_format={"type": "json_object"},
        )

    @patch("ai_splitter.load_openai_key", return_value="")
    def test_split_thread_no_api_key(self, mock_load_key):
        """Test that a ValueError is raised if the API key is missing."""
        with self.assertRaisesRegex(ValueError, "OpenAI API key not found"):
            split_thread_with_ai("Some text", model="gpt-4o-mini", language="English", extra_instructions="")

    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_invalid_json(self, mock_openai_class, mock_load_key):
        """Test that a RuntimeError is raised if the AI returns invalid JSON."""
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is not JSON"
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaisesRegex(RuntimeError, "The AI returned an invalid JSON format."):
            split_thread_with_ai("Some text", model="gpt-4o-mini", language="English", extra_instructions="")

    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_missing_threads_key(self, mock_openai_class, mock_load_key):
        """Test that a RuntimeError is raised if the JSON is missing the 'threads' key."""
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"thread": ["Old format"]})
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaisesRegex(RuntimeError, "AI response JSON is not a list"):
            split_thread_with_ai("Some text", model="gpt-4o-mini", language="English", extra_instructions="")

    @patch("ai_splitter.load_openai_key", return_value="fake_api_key")
    @patch("ai_splitter.openai.OpenAI")
    def test_split_thread_malformed_inner_structure(self, mock_openai_class, mock_load_key):
        """Test that a RuntimeError is raised if the inner structure is not a list of strings."""
        mock_client = mock_openai_class.return_value
        mock_response = MagicMock()
        # Valid JSON, but inner structure is not a list of lists of strings
        mock_response.choices[0].message.content = json.dumps({"threads": [["A good thread"], "not a thread"]})
        mock_client.chat.completions.create.return_value = mock_response

        with self.assertRaisesRegex(RuntimeError, "AI response is not a valid JSON array of string arrays."):
            split_thread_with_ai("Some text", model="gpt-4o-mini", language="English", extra_instructions="")