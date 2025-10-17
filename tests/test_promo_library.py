import json
import os
import unittest
from unittest.mock import patch, mock_open

import json
from typing import Dict, Any, List
from promo_library import (
    add_promo,
    delete_promo,
    get_all_promos,
)
from unittest.mock import patch, MagicMock


class TestPromoLibrary(unittest.TestCase):
    """Test suite for the promotional tweet library."""

    @patch("promo_library.upload_image")
    @patch("promo_library.write_file_content")
    @patch("promo_library.read_file_content")
    @patch("promo_library.find_file_in_folder")
    @patch("promo_library.get_or_create_workspace_folder")
    @patch("promo_library.get_drive_service")
    def test_add_promo_creates_file_and_adds_promo(
        self,
        mock_get_service,
        mock_get_folder,
        mock_find_file,
        mock_read_content,
        mock_write_content,
        mock_upload_image,
    ) -> None:
        """Test that adding a promo creates the file and adds the first item."""
        # --- Mocks ---
        mock_get_service.return_value = MagicMock()
        mock_get_folder.return_value = "fake_workspace_id"
        mock_find_file.return_value = None  # No existing file
        mock_read_content.return_value = None  # No content to read
        mock_upload_image.return_value = "fake_image_id"

        # Capture what's written
        def capture_write(*args, **kwargs):
            self.written_content = args[2]
            return "new_file_id"
        mock_write_content.side_effect = capture_write

        # --- Test ---
        add_promo("This is a test promo.", "/path/to/image.png")

        # --- Assertions ---
        mock_write_content.assert_called_once()
        written_data = json.loads(self.written_content)
        self.assertIn("promotions", written_data)
        promos = written_data["promotions"]
        self.assertEqual(len(promos), 1)
        self.assertEqual(promos[0]["text"], "This is a test promo.")
        self.assertEqual(promos[0]["image_id"], "fake_image_id")
        self.assertEqual(promos[0]["image_filename"], "image.png")

    @patch("promo_library.get_drive_service", return_value=MagicMock())
    def test_add_promo_with_empty_text_raises_error(self, mock_get_service) -> None:
        """Test that adding a promo with empty text raises a ValueError."""
        with self.assertRaises(ValueError):
            add_promo("")

    @patch("promo_library.upload_image")
    @patch("promo_library.write_file_content")
    @patch("promo_library.read_file_content")
    @patch("promo_library.find_file_in_folder")
    @patch("promo_library.get_or_create_workspace_folder")
    @patch("promo_library.get_drive_service")
    def test_delete_promo_removes_correct_item(
        self,
        mock_get_service,
        mock_get_folder,
        mock_find_file,
        mock_read_content,
        mock_write_content,
        mock_upload_image,
    ) -> None:
        """Test that a specific promo can be deleted."""
        # --- Mocks ---
        mock_get_service.return_value = MagicMock()
        mock_get_folder.return_value = "fake_workspace_id"
        mock_find_file.return_value = "fake_file_id"
        mock_upload_image.return_value = "fake_image_id_2"

        initial_promos = [
            {"text": "Promo to keep.", "image_id": "fake_image_id_1", "image_filename": "keep.png"},
            {"text": "Promo to delete.", "image_id": "fake_image_id_2", "image_filename": "delete.png"},
            {"text": "Another to keep.", "image_id": "fake_image_id_3", "image_filename": "keep2.png"},
        ]
        mock_read_content.return_value = json.dumps({"promotions": initial_promos})

        def capture_write(*args, **kwargs):
            self.written_content = args[2]
            return "new_file_id"
        mock_write_content.side_effect = capture_write

        promo_to_delete = {"text": "Promo to delete.", "image_id": "fake_image_id_2", "image_filename": "delete.png"}

        # --- Test ---
        delete_promo(promo_to_delete)

        # --- Assertions ---
        mock_write_content.assert_called_once()
        written_data = json.loads(self.written_content)
        final_promos = written_data["promotions"]
        self.assertEqual(len(final_promos), 2)
        self.assertNotIn(promo_to_delete, final_promos)
        self.assertEqual(final_promos[0]["text"], "Promo to keep.")
        self.assertEqual(final_promos[1]["text"], "Another to keep.")

    @patch("promo_library.find_file_in_folder", return_value=None)
    @patch("promo_library.get_or_create_workspace_folder")
    @patch("promo_library.get_drive_service")
    def test_get_all_promos_returns_empty_list_if_no_file(
        self, mock_get_service, mock_get_folder, mock_find_file
    ) -> None:
        """Test that getting promos returns an empty list when the file doesn't exist in Drive."""
        mock_get_service.return_value = MagicMock()
        mock_get_folder.return_value = "fake_workspace_id"

        promos = get_all_promos()
        self.assertEqual(promos, [])


if __name__ == "__main__":
    unittest.main()