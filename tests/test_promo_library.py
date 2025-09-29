import json
import os
import unittest
from unittest.mock import patch, mock_open

from promo_library import (
    add_promo,
    delete_promo,
    get_all_promos,
    PROMOTIONS_FILE,
)


class TestPromoLibrary(unittest.TestCase):
    """Test suite for the promotional tweet library."""

    def setUp(self) -> None:
        """Set up for tests: clear the promotions file if it exists."""
        if os.path.exists(PROMOTIONS_FILE):
            os.remove(PROMOTIONS_FILE)

    def tearDown(self) -> None:
        """Tear down after tests: clear the promotions file."""
        if os.path.exists(PROMOTIONS_FILE):
            os.remove(PROMOTIONS_FILE)

    def test_add_promo_creates_file_and_adds_promo(self) -> None:
        """Test that adding a promo creates the file and adds the first item."""
        self.assertFalse(os.path.exists(PROMOTIONS_FILE))
        add_promo("This is a test promo.", "/path/to/image.png")

        self.assertTrue(os.path.exists(PROMOTIONS_FILE))
        promos = get_all_promos()
        self.assertEqual(len(promos), 1)
        self.assertEqual(promos[0]["text"], "This is a test promo.")
        self.assertEqual(promos[0]["image_path"], "/path/to/image.png")

    def test_add_multiple_promos(self) -> None:
        """Test that multiple promos can be added sequentially."""
        add_promo("First promo.")
        add_promo("Second promo.", "/path/to/image2.png")

        promos = get_all_promos()
        self.assertEqual(len(promos), 2)
        self.assertEqual(promos[0]["text"], "First promo.")
        self.assertIsNone(promos[0]["image_path"])
        self.assertEqual(promos[1]["text"], "Second promo.")
        self.assertEqual(promos[1]["image_path"], "/path/to/image2.png")

    def test_add_promo_with_empty_text_raises_error(self) -> None:
        """Test that adding a promo with empty text raises a ValueError."""
        with self.assertRaises(ValueError):
            add_promo("")

    def test_delete_promo_removes_correct_item(self) -> None:
        """Test that a specific promo can be deleted."""
        add_promo("Promo to keep.")
        promo_to_delete = {"text": "Promo to delete.", "image_path": "/path/to/delete.png"}
        add_promo(promo_to_delete["text"], promo_to_delete["image_path"])
        add_promo("Another one to keep.")

        self.assertEqual(len(get_all_promos()), 3)

        delete_promo(promo_to_delete)

        promos = get_all_promos()
        self.assertEqual(len(promos), 2)
        self.assertNotIn(promo_to_delete, promos)
        self.assertEqual(promos[0]["text"], "Promo to keep.")
        self.assertEqual(promos[1]["text"], "Another one to keep.")

    def test_delete_nonexistent_promo_does_nothing(self) -> None:
        """Test that attempting to delete a promo that doesn't exist does not alter the list."""
        add_promo("First promo.")
        add_promo("Second promo.")
        self.assertEqual(len(get_all_promos()), 2)

        delete_promo({"text": "Nonexistent promo.", "image_path": None})

        self.assertEqual(len(get_all_promos()), 2)

    def test_get_all_promos_returns_empty_list_if_no_file(self) -> None:
        """Test that getting promos returns an empty list when the file doesn't exist."""
        self.assertFalse(os.path.exists(PROMOTIONS_FILE))
        self.assertEqual(get_all_promos(), [])

    @patch("builtins.open", new_callable=mock_open, read_data="[invalid json")
    def test_get_all_promos_handles_json_decode_error(self, mock_file) -> None:
        """Test that a JSON decode error is handled gracefully."""
        # Ensure the mock is used for the file read
        with patch("os.path.exists", return_value=True):
            promos = get_all_promos()
            self.assertEqual(promos, [])

    @patch("builtins.open", new_callable=mock_open)
    def test_save_promos_handles_io_error(self, mock_open_file) -> None:
        """Test that an IO error during save is handled gracefully."""
        mock_open_file.side_effect = IOError("Disk full")

        # This should not raise an exception
        with self.assertLogs('promo_library', level='ERROR') as cm:
            add_promo("This should fail to save")
            self.assertIn("Error saving promotions file", cm.output[0])


if __name__ == "__main__":
    unittest.main()