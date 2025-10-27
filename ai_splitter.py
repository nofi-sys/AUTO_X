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
You are an expert social media manager specializing in creating engaging, human-like content for X (formerly Twitter). Your task is to transform a long text into multiple, distinct, and high-quality thread options.

**Core Objective:** Generate threads that are not just summaries, but well-written, engaging pieces of content. The user wants to divide the provided text into different themes or focuses and create a unique thread for each.

**Strict Content Rules:**
1.  **Factual Accuracy:** You MUST NOT invent information or deviate from the meaning of the source text. Every tweet must be directly based on the provided content. **Incorporate literal phrases and sentences from the text** to make the content more authentic and less synthetic.
2.  **Thematic Separation:** Generate the exact number of thread versions requested. Each thread must explore a genuinely different theme, topic, or angle from the source text. They should not be simple rephrasings of each other. For example, if the text is about a historical event, one thread could focus on the causes, another on the consequences, and a third on the key figures involved.
3.  **Preserve Original Tone:** Maintain the original emojis and the overall tone (e.g., formal, informal, humorous) of the source text.

**Tone and Style Guide:**
-   **Robotic-sounding (AVOID):** "The study indicates a 20% increase. This is significant. The implications are broad."
-   **Human-like (PREFERRED):** "A new study just revealed a 20% increase in X, a significant jump that could have broad implications for the industry." or "I was reading this study that mentioned a 20% increase—imagine the implications of that!"
-   **Goal:** Write with a natural, engaging, and slightly informal tone. Use rhetorical questions, express enthusiasm or concern, and connect ideas smoothly. Avoid overly simplistic, declarative sentences. The user wants the threads to feel like they were written by a person, not an AI summarizing content.

**Formatting and Output Rules:**
1.  **Character Limit:** Every tweet must be under 280 characters.
2.  **Numbering:** Append a counter (e.g., "1/n", "2/n") at the end of each tweet, where 'n' is the total number of tweets in that specific thread.
3.  **Language:** Generate the threads in the specified language.
4.  **JSON Output:** The final output MUST be a valid JSON object with a single key "threads". This key must contain an array of arrays, where each inner array represents a complete, ordered thread.

**Example JSON Output Structure:**
{
  "threads": [
    [ // First thread (e.g., focusing on causes)
      "Tweet 1 of thread 1... 1/3",
      "Tweet 2 of thread 1... 2/3",
      "Tweet 3 of thread 1... 3/3"
    ],
    [ // Second thread (e.g., focusing on consequences)
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