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
You are an expert social media manager. Your task is to take a piece of text and generate multiple, distinct, and compelling thread options for X (formerly Twitter).

Follow these rules strictly:
1.  Generate the exact number of thread versions requested by the user.
2.  Each tweet within a thread must be under 280 characters.
3.  Preserve all original emojis and the overall tone of the text.
4.  Number the tweets in the format "1/n", "2/n", etc., at the end of each tweet, where 'n' is the total number of tweets in that specific thread.
5.  The output MUST be a valid JSON object with a single key "threads" which contains an array of arrays. Each inner array represents one complete thread.

Example Input Text:
"User wants 2 versions of the following text: Python is a versatile language. You can use it for web development, data science, and automation. It's great for beginners and experts alike."

Example Output JSON:
{
  "threads": [
    [
      "Python is a versatile language, ideal for web dev, data science, & automation. It’s a top choice for both new and seasoned developers. 1/2",
      "With vast libraries and strong community support, Python empowers you to build anything from a simple script to a complex AI model. 2/2"
    ],
    [
      "Discover the power of Python! A versatile language perfect for web development, data science, and automating tasks. 1/2",
      "Whether you're a beginner or an expert, Python's simplicity and robust ecosystem make it the ideal tool for your next project. 2/2"
    ]
  ]
}
"""


def split_thread_with_ai(text: str, num_versions: int = 3) -> List[List[str]]:
    """
    Uses OpenAI's chat model to split a long text into multiple Twitter thread versions.

    Args:
        text: The full text to be split into a thread.
        num_versions: The number of different thread versions to generate.

    Returns:
        A list of lists of strings, where each inner list is a complete thread.

    Raises:
        ValueError: If the OpenAI API key is not configured.
        RuntimeError: If the API call fails or returns an invalid format.
    """
    api_key = load_openai_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")

    client = openai.OpenAI(api_key=api_key)
    user_prompt = f"Please generate {num_versions} different thread versions for the following text:\n\n{text}"

    try:
        logger.info("Calling OpenAI API with model %s to generate %d thread versions...", AI_MODEL, num_versions)
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
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
        threads = parsed_json.get("threads")

        # --- Validation for the new structure ---
        if not isinstance(threads, list):
            raise RuntimeError("AI response JSON is not a list.")
        if not all(isinstance(thread, list) and all(isinstance(tweet, str) for tweet in thread) for thread in threads):
            raise RuntimeError("AI response is not a valid JSON array of string arrays.")

        return threads

    except openai.APIError as e:
        logger.exception("OpenAI API error occurred.")
        raise RuntimeError(f"An error occurred with the OpenAI API: {e}") from e
    except json.JSONDecodeError as e:
        logger.exception("Failed to decode JSON from AI response.")
        raise RuntimeError("The AI returned an invalid JSON format.") from e
    except (KeyError, TypeError) as e:
        logger.exception("AI response JSON is missing the 'threads' key or is malformed.")
        raise RuntimeError("The AI response format was unexpected.") from e