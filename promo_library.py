import json
import logging
import os
from typing import List, Dict, Optional, Any

# Configure logging
logger = logging.getLogger(__name__)

PROMOTIONS_FILE = "promotions.json"


def _get_promotions() -> List[Dict[str, Optional[str]]]:
    """Load all promotional tweets from the JSON file."""
    if not os.path.exists(PROMOTIONS_FILE):
        return []
    try:
        with open(PROMOTIONS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading promotions file: {e}")
        return []


def _save_promotions(promotions: List[Dict[str, Optional[str]]]) -> None:
    """Save the list of promotional tweets to the JSON file."""
    try:
        with open(PROMOTIONS_FILE, "w") as f:
            json.dump(promotions, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving promotions file: {e}")


def get_all_promos() -> List[Dict[str, Optional[str]]]:
    """Return a list of all saved promotional tweets."""
    return _get_promotions()


def add_promo(text: str, image_path: Optional[str] = None) -> None:
    """
    Add a new promotional tweet to the library.

    Args:
        text: The text content of the promotional tweet.
        image_path: The optional file path to an associated image.
    """
    if not text:
        raise ValueError("Promotional text cannot be empty.")

    promotions = _get_promotions()
    new_promo = {"text": text, "image_path": image_path}
    promotions.append(new_promo)
    _save_promotions(promotions)
    logger.info("Added new promotion: %s", text[:50])


def delete_promo(promo_to_delete: Dict[str, Any]) -> None:
    """
    Delete a specific promotional tweet from the library.

    The matching is done based on both text and image_path to ensure
    the correct item is removed.
    """
    promotions = _get_promotions()
    # Normalize the promo to delete for consistent matching (e.g., handle None vs. missing keys)
    normalized_promo_to_delete = {
        "text": promo_to_delete.get("text"),
        "image_path": promo_to_delete.get("image_path"),
    }

    # Re-create the list, excluding the promo that matches the one to be deleted
    updated_promotions = [
        p for p in promotions
        if not (p.get("text") == normalized_promo_to_delete["text"] and p.get("image_path") == normalized_promo_to_delete["image_path"])
    ]

    if len(updated_promotions) < len(promotions):
        _save_promotions(updated_promotions)
        logger.info("Deleted promotion: %s", normalized_promo_to_delete["text"][:50])
    else:
        logger.warning("Could not find the specified promotion to delete.")