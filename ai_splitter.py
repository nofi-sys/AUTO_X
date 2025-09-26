import json
import logging
from typing import List

import openai

from config import load_openai_key

# Configure logging
logger = logging.getLogger(__name__)

# Note: User requested gpt5-mini, but as of now, the most advanced compact model is in the GPT-4 series.
# Using gpt-4o-mini as a powerful and cost-effective alternative.
AI_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """
You are an expert social media manager. Your task is to take a piece of text and split it into a compelling, coherent, and well-structured thread for X (formerly Twitter).

Follow these rules strictly:
1.  Each tweet must be under 280 characters.
2.  Preserve all original emojis and the overall tone of the text.
3.  Number the tweets in the format "1/n", "2/n", etc., at the end of each tweet, where 'n' is the total number of tweets in the thread.
4.  The output MUST be a valid JSON object with a single key "thread" which contains an array of strings. Each string is one tweet.

Example Input Text:
"Python is a versatile language. You can use it for web development, data science, and automation. It's great for beginners and experts alike."

Example Output JSON:
{
  "thread": [
    "Python is a versatile language. You can use it for web development, data science, and automation. It's great for beginners and experts alike. 1/2",
    "Whether you're building a simple script or a complex machine learning model, Python has the libraries and community support to get the job done. 2/2"
  ]
}
"""


def split_thread_with_ai(text: str) -> List[str]:
    """
    Uses OpenAI's chat model to split a long text into a Twitter thread.

    Args:
        text: The full text to be split into a thread.

    Returns:
        A list of strings, where each string is a tweet.

    Raises:
        ValueError: If the OpenAI API key is not configured.
        RuntimeError: If the API call fails or returns an invalid format.
    """
    api_key = load_openai_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")

    client = openai.OpenAI(api_key=api_key)

    try:
        logger.info("Calling OpenAI API with model %s to split thread...", AI_MODEL)
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        logger.info("Successfully received response from OpenAI API.")

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Received an empty response from the AI.")

        # Parse the JSON response
        parsed_json = json.loads(content)
        thread = parsed_json.get("thread")

        if not isinstance(thread, list) or not all(isinstance(t, str) for t in thread):
            raise RuntimeError("AI response is not a valid JSON array of strings.")

        return thread

    except openai.APIError as e:
        logger.exception("OpenAI API error occurred.")
        raise RuntimeError(f"An error occurred with the OpenAI API: {e}") from e
    except json.JSONDecodeError as e:
        logger.exception("Failed to decode JSON from AI response.")
        raise RuntimeError("The AI returned an invalid JSON format.") from e
    except (KeyError, TypeError) as e:
        logger.exception("AI response JSON is missing the 'thread' key or is malformed.")
        raise RuntimeError("The AI response format was unexpected.") from e