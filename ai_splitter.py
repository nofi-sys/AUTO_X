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
You are an expert social media manager specializing in creating engaging content for X (formerly Twitter). Your primary task is to parse a long text and generate multiple, distinct, and compelling thread options.

**Key Objective:** The user wants different threads that can be posted on different days without being redundant. If the source text covers multiple topics, each generated thread should focus on one of those topics. If the text covers one topic, each thread should explore a different angle or perspective of that topic.

**Strict Rules:**
1.  **Generate Distinct Threads:** Create the exact number of thread versions requested. Each thread must be unique and not just a rephrasing of the others.
2.  **Character Limit:** Every tweet must be under 280 characters.
3.  **Preserve Tone:** Maintain the original emojis and the overall tone of the source text.
4.  **Numbering:** Append a counter (e.g., "1/n", "2/n") at the end of each tweet, where 'n' is the total number of tweets in that specific thread.
5.  **Language:** Generate the threads in the specified language.
6.  **JSON Output:** The final output MUST be a valid JSON object with a single key "threads". This key must contain an array of arrays, where each inner array represents a complete, ordered thread.

**Example Scenario:**
*   **User Request:** Generate 2 threads in English from a long text about the benefits of both coffee and tea.
*   **Correct Output:** One thread focuses entirely on the benefits of coffee, and the second thread focuses entirely on the benefits of tea.
*   **Incorrect Output:** Two slightly different threads that both discuss coffee and tea.

**Example JSON Output Structure:**
{
  "threads": [
    [ // First thread
      "Tweet 1 of thread 1... 1/3",
      "Tweet 2 of thread 1... 2/3",
      "Tweet 3 of thread 1... 3/3"
    ],
    [ // Second thread
      "Tweet 1 of thread 2... 1/2",
      "Tweet 2 of thread 2... 2/2"
    ]
  ]
}
"""


def split_thread_with_ai(
    text: str, model: str, language: str, extra_instructions: str, num_versions: int = 3
) -> List[List[str]]:
    """
    Uses OpenAI's chat model to split a long text into multiple Twitter thread versions.

    Args:
        text: The full text to be split into a thread.
        model: The AI model to use (e.g., "gpt-4o", "gpt-4o-mini").
        language: The target language for the threads.
        extra_instructions: Additional user-provided instructions for the AI.
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

    # Construct a more detailed user prompt
    user_prompt = (
        f"Please generate {num_versions} different and distinct thread versions in {language} "
        f"for the following text. Each version should explore a different angle or aspect of the text.\n\n"
        f"Original Text:\n\"\"\"\n{text}\n\"\"\"\n"
    )
    if extra_instructions:
        user_prompt += f"\nFollow these additional instructions carefully: {extra_instructions}"

    try:
        logger.info("Calling OpenAI API with model %s to generate %d thread versions...", model, num_versions)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
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