import json
import logging
import os
from typing import List, Dict, Optional, Any

from google_drive_api import (
    get_drive_service,
    get_or_create_workspace_folder,
    find_file_in_folder,
    read_file_content,
    write_file_content,
    upload_image,
    delete_file,
)

# Configure logging
logger = logging.getLogger(__name__)

PROMOTIONS_FILE = "promotions.json"


def _get_promotions() -> List[Dict[str, Optional[str]]]:
    """Load all promotional tweets from the JSON file in Google Drive."""
    drive_service = get_drive_service()
    if not drive_service:
        logger.error("Cannot get promotions: Google Drive service is not available.")
        return []

    try:
        workspace_id = get_or_create_workspace_folder(drive_service)
    except ConnectionError as exc:
        logger.error("Cannot get promotions: %s", exc)
        return []
    if not workspace_id:
        logger.error("Cannot get promotions: Google Drive workspace folder is not available.")
        return []

    promo_file_id = find_file_in_folder(drive_service, PROMOTIONS_FILE, workspace_id)
    if not promo_file_id:
        logger.info(f"'{PROMOTIONS_FILE}' not found in Drive. Returning empty list.")
        return []

    try:
        content = read_file_content(drive_service, promo_file_id)
        if content:
            data = json.loads(content)
            # Handle legacy format where the file was just a list of promotions
            if isinstance(data, list):
                return data
            return data.get("promotions", [])
        return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading or parsing promotions file from Drive: {e}")
        return []


def _save_promotions(promotions: List[Dict[str, Optional[str]]]) -> None:
    """Save the list of promotional tweets to the JSON file in Google Drive."""
    drive_service = get_drive_service()
    if not drive_service:
        logger.error("Cannot save promotions: Google Drive service is not available.")
        return

    try:
        workspace_id = get_or_create_workspace_folder(drive_service)
    except ConnectionError as exc:
        logger.error("Cannot save promotions: %s", exc)
        return
    if not workspace_id:
        logger.error("Cannot save promotions: Google Drive workspace folder is not available.")
        return

    promo_file_id = find_file_in_folder(drive_service, PROMOTIONS_FILE, workspace_id)
    content = json.dumps({"promotions": promotions}, indent=2)

    write_file_content(drive_service, PROMOTIONS_FILE, content, workspace_id, promo_file_id)


def get_all_promos() -> List[Dict[str, Optional[str]]]:
    """Return a list of all saved promotional tweets from Google Drive."""
    return _get_promotions()


def add_promo(text: str, image_path: Optional[str] = None) -> None:
    """
    Add a new promotional tweet to the library in Google Drive.

    Args:
        text: The text content of the promotional tweet.
        image_path: The optional local file path to an associated image.
    """
    if not text:
        raise ValueError("Promotional text cannot be empty.")

    drive_service = get_drive_service()
    workspace_id = None
    if drive_service:
        try:
            workspace_id = get_or_create_workspace_folder(drive_service)
        except ConnectionError as exc:
            raise ConnectionError(str(exc)) from exc

    if image_path and (not drive_service or not workspace_id):
        raise ConnectionError("Cannot upload image: Google Drive service is not available.")

    image_id = None
    image_filename = None
    if image_path:
        image_filename = os.path.basename(image_path)
        logger.info(f"Uploading image '{image_path}' to Google Drive...")
        image_id = upload_image(drive_service, image_path, workspace_id)
        if not image_id:
            raise IOError(f"Failed to upload image '{image_filename}' to Google Drive.")

    promotions = _get_promotions()
    # Note: We now store the Google Drive file ID and original filename for the image
    new_promo = {"text": text, "image_id": image_id, "image_filename": image_filename}
    promotions.append(new_promo)
    _save_promotions(promotions)
    logger.info("Added new promotion to Google Drive: %s", text[:50])


def delete_promo(promo_to_delete: Dict[str, Any]) -> None:
    """
    Delete a specific promotional tweet from the library in Google Drive.

    If the promotion has an associated image, it will also be deleted.
    """
    promotions = _get_promotions()

    image_id_to_delete = promo_to_delete.get("image_id")

    # Re-create the list, excluding the promo that matches the one to be deleted
    updated_promotions = [
        p for p in promotions
        if not (p.get("text") == promo_to_delete.get("text") and p.get("image_id") == image_id_to_delete)
    ]

    if len(updated_promotions) < len(promotions):
        _save_promotions(updated_promotions)
        logger.info("Deleted promotion from JSON: %s", promo_to_delete.get("text", "")[:50])

        # If an image was associated, delete it from Google Drive
        if image_id_to_delete:
            drive_service = get_drive_service()
            if drive_service:
                logger.info(f"Deleting associated image with ID: {image_id_to_delete}")
                delete_file(drive_service, image_id_to_delete)
            else:
                logger.warning(f"Could not delete image '{image_id_to_delete}' because Drive service is unavailable.")
    else:
        logger.warning("Could not find the specified promotion to delete.")
