"""Tkinter GUI for composing X (Twitter) threads."""

import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import List, Optional

from dotenv import load_dotenv

from ai_splitter import split_thread_with_ai
from config import load_twitter_credentials
from plain_thread import parse_plain_thread
from promo_library import add_promo, delete_promo, get_all_promos
from twitter_api import publish_thread

logging.basicConfig(level=logging.INFO)


def _center_window(win: tk.Toplevel) -> None:
    """Center a Toplevel window on its parent."""
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


class CredentialsDialog(tk.Toplevel):
    """Dialog for entering and saving Twitter API credentials."""

    def __init__(self, parent: tk.Tk) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Enter Credentials")
        self.parent = parent
        self.result: Optional[List[str]] = None

        # ─── Widgets ──────────────────────────────────────────────────────────
        body = ttk.Frame(self)
        self.initial_focus = self._create_widgets(body)
        body.pack(padx=20, pady=20)
        self._create_buttons()

        # ─── Dialog Behavior ──────────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> ttk.Widget:
        """Create the input fields for the credentials."""
        ttk.Label(master, text="Enter your Twitter/X API credentials:").grid(row=0, columnspan=2, sticky="w")

        labels = ("API Key", "API Secret", "Access Token", "Access Secret")
        self.entries: List[ttk.Entry] = []
        for i, label in enumerate(labels):
            ttk.Label(master, text=f"{label}:").grid(row=i + 1, column=0, sticky="w", padx=5, pady=5)
            entry = ttk.Entry(master, width=50)
            entry.grid(row=i + 1, column=1, sticky="ew", padx=5, pady=5)
            self.entries.append(entry)

        return self.entries[0]

    def _create_buttons(self) -> None:
        """Create the 'Save' and 'Cancel' buttons."""
        box = ttk.Frame(self)
        save_btn = ttk.Button(box, text="Save", command=self._save, default=tk.ACTIVE)
        cancel_btn = ttk.Button(box, text="Cancel", command=self._cancel)
        save_btn.pack(side=tk.LEFT, padx=5, pady=10)
        cancel_btn.pack(side=tk.RIGHT, padx=5, pady=10)
        box.pack()

    def _save(self, event: Optional[tk.Event] = None) -> None:
        """Handle the 'Save' button click."""
        self.result = [entry.get() for entry in self.entries]
        if not all(self.result):
            messagebox.showwarning("Missing fields", "All credential fields are required.", parent=self)
            return

        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

    def _cancel(self, event: Optional[tk.Event] = None) -> None:
        """Handle the 'Cancel' button click or window close."""
        self.result = None
        self.parent.focus_set()
        self.destroy()


MAX_TWEET_LEN = 280  # Twitter/X character limit


class ThreadSelectionDialog(tk.Toplevel):
    """Dialog for selecting one of multiple AI-generated thread versions."""

    def __init__(self, parent: tk.Tk, threads: List[List[str]]) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Select an AI-Generated Thread")
        self.parent = parent
        self.threads = threads
        self.result: Optional[List[str]] = None

        # ─── Widgets ──────────────────────────────────────────────────────────
        body = ttk.Frame(self)
        self._create_widgets(body)
        body.pack(padx=20, pady=20, expand=True, fill="both")

        # ─── Dialog Behavior ──────────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> None:
        """Create the tabbed view for thread selection."""
        ttk.Label(master, text="Select the thread version you want to use:").pack(pady=(0, 10))

        notebook = ttk.Notebook(master)
        notebook.pack(pady=5, padx=5, expand=True, fill="both")

        for i, thread in enumerate(self.threads):
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=f"Version {i + 1}")

            text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=15, width=80)
            full_thread_text = "\n\n".join(thread)
            text_area.insert(tk.END, full_thread_text)
            text_area.configure(state="disabled")
            text_area.pack(expand=True, fill="both")

        # --- Buttons ---
        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=(10, 0))
        select_btn = ttk.Button(btn_frame, text="Select this Thread", command=lambda: self._select(notebook.index(notebook.select())))
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._cancel)
        select_btn.pack(side="left", padx=10)
        cancel_btn.pack(side="right", padx=10)

    def _select(self, selected_index: int) -> None:
        """Handle the 'Select' button click."""
        self.result = self.threads[selected_index]
        self.destroy()

    def _cancel(self) -> None:
        """Handle the 'Cancel' button click or window close."""
        self.result = None
        self.destroy()


class AddPromoDialog(tk.Toplevel):
    """Dialog for adding a new promotional tweet."""

    def __init__(self, parent: tk.Toplevel) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Add New Promotion")
        self.parent = parent
        self.result: Optional[tuple[str, Optional[str]]] = None
        self.image_path: Optional[str] = None

        # --- Widgets ---
        body = ttk.Frame(self)
        self._create_widgets(body)
        body.pack(padx=20, pady=20)

        # --- Dialog Behavior ---
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> None:
        """Create the input fields for the new promotion."""
        ttk.Label(master, text="Promotional Tweet Text:").pack(anchor="w")
        self.text_entry = scrolledtext.ScrolledText(master, height=5, width=60, wrap=tk.WORD)
        self.text_entry.pack(pady=(0, 10), fill="both", expand=True)

        # --- Image Selection ---
        image_frame = ttk.Frame(master)
        image_frame.pack(fill="x", expand=True)
        self.image_label = ttk.Label(image_frame, text="Image: (None)")
        self.image_label.pack(side="left")
        ttk.Button(image_frame, text="Attach Image...", command=self._attach_image).pack(side="right")

        # --- Buttons ---
        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="right", padx=10)

    def _attach_image(self) -> None:
        """Open file dialog to select an image."""
        path = filedialog.askopenfilename(
            title="Select image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")]
        )
        if path:
            self.image_path = path
            self.image_label.config(text=f"Image: {os.path.basename(path)}")

    def _save(self) -> None:
        """Save the new promotion."""
        text = self.text_entry.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Text Required", "Promotional text cannot be empty.", parent=self)
            return
        if len(text) > MAX_TWEET_LEN:
            messagebox.showwarning("Too Long", f"The text must be under {MAX_TWEET_LEN} characters.", parent=self)
            return

        self.result = (text, self.image_path)
        self.destroy()

    def _cancel(self) -> None:
        """Cancel adding a promotion."""
        self.result = None
        self.destroy()


class SelectPromoDialog(tk.Toplevel):
    """Dialog for selecting a promotional tweet to append to a thread."""

    def __init__(self, parent: tk.Tk) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Select Promotional Tweet")
        self.parent = parent
        self.promos = get_all_promos()
        self.result: Optional[dict] = None

        # --- Widgets ---
        body = ttk.Frame(self)
        self._create_widgets(body)
        body.pack(padx=20, pady=20, expand=True, fill="both")

        # --- Dialog Behavior ---
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> None:
        """Create the listbox and buttons for promo selection."""
        ttk.Label(master, text="Select a promotion to add to your thread:").pack(anchor="w")

        # --- Listbox ---
        list_frame = ttk.Frame(master)
        list_frame.pack(pady=5, expand=True, fill="both")
        self.promo_listbox = tk.Listbox(list_frame, height=10, width=80)
        self.promo_listbox.pack(side="left", expand=True, fill="both")

        for promo in self.promos:
            has_image = promo.get("image_path")
            image_info = f"[Image: {os.path.basename(has_image)}]" if has_image else "[No Image]"
            display_text = f"{promo.get('text', '')[:80]}... - {image_info}"
            self.promo_listbox.insert(tk.END, display_text)

        # --- Buttons ---
        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text="Select", command=self._select).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="right", padx=10)

    def _select(self) -> None:
        """Set the selected promotion as the result and close."""
        selected_indices = self.promo_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select a promotion.", parent=self)
            return
        self.result = self.promos[selected_indices[0]]
        self.destroy()

    def _cancel(self) -> None:
        """Cancel the selection."""
        self.result = None
        self.destroy()


class PromoManagerDialog(tk.Toplevel):
    """Dialog for managing the promotional tweet library."""

    def __init__(self, parent: tk.Tk) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Manage Promotions")
        self.parent = parent
        self.promos = []

        # --- Widgets ---
        body = ttk.Frame(self)
        self._create_widgets(body)
        body.pack(padx=20, pady=20, expand=True, fill="both")

        # --- Dialog Behavior ---
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> None:
        """Create the widgets for managing promotions."""
        ttk.Label(master, text="Saved Promotional Tweets:").pack(anchor="w")

        # --- Listbox for promos ---
        list_frame = ttk.Frame(master)
        list_frame.pack(pady=5, expand=True, fill="both")
        self.promo_listbox = tk.Listbox(list_frame, height=10, width=80)
        self.promo_listbox.pack(side="left", expand=True, fill="both")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.promo_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.promo_listbox.config(yscrollcommand=scrollbar.set)

        self._refresh_promo_list()

        # --- Buttons ---
        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text="Add New...", command=self._add_promo_handler).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self._delete_promo_handler).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side="right", padx=5)

    def _refresh_promo_list(self) -> None:
        """Clear and reload the list of promotions from the library."""
        self.promo_listbox.delete(0, tk.END)
        self.promos = get_all_promos()
        for promo in self.promos:
            has_image = promo.get("image_path")
            image_info = f"[Image: {os.path.basename(has_image)}]" if has_image else "[No Image]"
            display_text = f"{promo.get('text', '')[:80]}... - {image_info}"
            self.promo_listbox.insert(tk.END, display_text)

    def _add_promo_handler(self) -> None:
        """Handle adding a new promotion."""
        dialog = AddPromoDialog(self)
        _center_window(dialog)
        if dialog.result:
            text, image_path = dialog.result
            try:
                add_promo(text, image_path)
                self._refresh_promo_list()
                messagebox.showinfo("Success", "Promotional tweet added.", parent=self)
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=self)

    def _delete_promo_handler(self) -> None:
        """Handle deleting a selected promotion."""
        selected_indices = self.promo_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select a promotion to delete.", parent=self)
            return

        selected_index = selected_indices[0]
        promo_to_delete = self.promos[selected_index]

        if messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete this promotion?\n\n{promo_to_delete.get('text', '')[:100]}...",
            parent=self,
        ):
            delete_promo(promo_to_delete)
            self._refresh_promo_list()


def split_text_into_tweets(text: str, limit: int = MAX_TWEET_LEN) -> List[str]:
    """Return a list of tweet-sized chunks from ``text``.

    The split respects word boundaries whenever possible and falls back to a
    hard cut if a single word is longer than ``limit``.
    """
    chunks: List[str] = []
    text = text.strip()
    while len(text) > limit:
        split_pos = text.rfind(" ", 0, limit)
        if split_pos == -1:  # no space found – hard split
            split_pos = limit
        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()
    if text:
        chunks.append(text)
    return chunks


class ThreadComposer(tk.Tk):
    """Tkinter window to compose and publish threads."""

    def __init__(self) -> None:
        """Initialize the GUI widgets and state."""
        super().__init__()
        self.title("Tweet Thread Composer")
        self.geometry("900x700")

        # Internal state
        self.tweets: List[str] = []
        self.images: List[Optional[str]] = []
        self.char_count_labels: List[ttk.Label] = []
        self.image_path_labels: List[ttk.Label] = []

        # Style for validation labels
        self.style = ttk.Style(self)
        self.style.configure("TLabel", padding=2)
        self.style.configure("Invalid.TLabel", foreground="red")
        self.style.configure("Valid.TLabel", foreground="black")

        self._build_widgets()

        # Warn user on startup if credentials are not configured
        self.after_idle(self._check_creds)

    def _configure_credentials(self) -> bool:
        """Open a dialog for the user to enter their credentials.

        If the user saves, the credentials will be written to a local ``.env``
        file and reloaded.
        """
        dialog = CredentialsDialog(self)
        _center_window(dialog)
        result = dialog.result
        if result:
            keys = ("TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET")
            with open(".env", "w") as f:
                for key, value in zip(keys, result):
                    f.write(f"{key}={value}\n")
            load_dotenv()  # Reload .env to update current session
            messagebox.showinfo("Success", "Credentials saved successfully.", parent=self)
            return True
        return False

    def _check_creds(self) -> None:
        """Check for credentials and prompt user if missing."""
        creds = load_twitter_credentials()
        if not all([creds.api_key, creds.api_secret, creds.access_token, creds.access_secret]):
            if messagebox.askyesno(
                "Missing Credentials",
                "Twitter API credentials are not fully set.\n\n"
                "You can compose a thread, but publishing will fail. "
                "Do you want to enter them now?",
            ):
                self._configure_credentials()

    def _open_promo_manager(self) -> None:
        """Open the dialog to manage promotional tweets."""
        dialog = PromoManagerDialog(self)
        _center_window(dialog)

    # ───────────────────────────────────────────────────── GUI CONSTRUCTION ────
    def _build_widgets(self) -> None:
        """Create and place the GUI widgets."""
        # ─── Menu Bar ─────────────────────────────────────────────────────────
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Configure Credentials...", command=self._configure_credentials)
        settings_menu.add_command(label="Manage Promotions...", command=self._open_promo_manager)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # ─── Main Widgets ─────────────────────────────────────────────────────
        # Input text area
        ttk.Label(self, text="Enter your full thread (blank line = manual break):").pack(anchor="w", padx=6, pady=(6, 0))
        self.input_box = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.input_box.pack(fill="x", padx=6, pady=6)

        ttk.Button(self, text="↳ Parse into Tweets", command=self._parse_handler).pack(pady=(0, 4))
        ttk.Button(self, text="🡆 Parse Plain-Thread", command=self._parse_plain_handler).pack(pady=(0, 4))
        ttk.Button(self, text="✨ Generate with AI", command=self._parse_with_ai_handler).pack(pady=(0, 8))

        # Dynamic container for tweet previews & image selectors
        self.tweets_frame = ttk.Frame(self)
        self.tweets_frame.pack(fill="both", expand=True, padx=6, pady=6)

        # --- Action Buttons ---
        action_frame = ttk.Frame(self)
        action_frame.pack(pady=(4, 10))

        self.add_promo_btn = ttk.Button(action_frame, text="Add Promotional Tweet", command=self._add_promo_tweet_handler)
        self.add_promo_btn.pack(side="left", padx=10)
        self.publish_btn = ttk.Button(action_frame, text="🚀 Publish Thread", state="disabled", command=self._publish_handler)
        self.publish_btn.pack(side="left", padx=10)

    # ───────────────────────────────────────────────────── EVENT HANDLERS ────
    def _add_promo_tweet_handler(self) -> None:
        """Open a dialog to select and append a promotional tweet."""
        if not self.tweets:
            messagebox.showwarning("No Thread", "You must parse or generate a thread first.", parent=self)
            return

        dialog = SelectPromoDialog(self)
        _center_window(dialog)
        if dialog.result:
            promo = dialog.result
            self.tweets.append(promo["text"])
            self.images.append(promo.get("image_path"))
            self._render_tweets(self.tweets)  # Re-render the entire thread
            messagebox.showinfo("Success", "Promotional tweet added to the end of the thread.", parent=self)

    def _parse_handler(self) -> None:
        """Split the text box contents into individual tweets."""
        raw = self.input_box.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Nothing to parse", "Write something first!")
            return

        # Choose strategy: manual breaks (double‑newline) or auto‑split
        if "\n\n" in raw:
            tweets = [seg.strip() for seg in raw.split("\n\n") if seg.strip()]
        else:
            tweets = split_text_into_tweets(raw)
        logging.info("Parsed %d tweets", len(tweets))

        # Guard against empty list or too many tweets (Twitter caps at 25 in UI)
        if not tweets:
            messagebox.showerror("Parse error", "Could not split text into tweets.")
            return
        if len(tweets) > 50:
            if not messagebox.askyesno("Long thread", f"You are about to post {len(tweets)} tweets. Continue?"):
                return

        self._render_tweets(tweets)

    def _parse_plain_handler(self) -> None:
        """Parse the text using the Plain-Thread v1 format."""
        raw = self.input_box.get("1.0", tk.END)
        try:
            tweets = parse_plain_thread(raw)
        except Exception as exc:  # pragma: no cover - Tkinter errors not easily testable
            messagebox.showerror("Parse error", str(exc))
            return
        if len(tweets) > 50:
            if not messagebox.askyesno("Long thread", f"You are about to post {len(tweets)} tweets. Continue?"):
                return
        self._render_tweets(tweets)

    def _parse_with_ai_handler(self) -> None:
        """Use the AI splitter to generate multiple thread options from the input text."""
        raw = self.input_box.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Nothing to generate", "Write something first!")
            return

        self.config(cursor="watch")
        self.update_idletasks()

        try:
            # Generate multiple thread versions (e.g., 3)
            threads = split_thread_with_ai(raw, num_versions=3)
            logging.info("Generated %d thread versions with AI", len(threads))

            if not threads:
                messagebox.showerror("AI Error", "The AI returned no threads.")
                return

            # Open the selection dialog
            dialog = ThreadSelectionDialog(self, threads)
            _center_window(dialog)
            selected_thread = dialog.result

            if selected_thread:
                self._render_tweets(selected_thread)

        except (ValueError, RuntimeError) as exc:
            logging.exception("Failed to generate thread with AI")
            messagebox.showerror("AI Generation Failed", str(exc))
        finally:
            self.config(cursor="")

    def _render_tweets(self, tweets: List[str]) -> None:
        """Display parsed tweets in the preview list."""
        for w in self.tweets_frame.winfo_children():
            w.destroy()

        self.tweets = tweets
        self.images = [None] * len(tweets)
        self.char_count_labels = []
        self.image_path_labels = []

        for idx, txt in enumerate(tweets):
            row = ttk.Frame(self.tweets_frame)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=f"{idx + 1:02d}.").pack(side="left", anchor="n", padx=(0, 4))

            # --- Tweet Content ---
            text_frame = ttk.Frame(row)
            text_frame.pack(side="left", fill="x", expand=True)
            preview = tk.Text(text_frame, height=min(6, (len(txt) // 50) + 1), width=70, wrap=tk.WORD)
            preview.insert("1.0", txt)
            preview.configure(state="disabled", background="#F7F7F7")
            preview.pack(side="top", fill="x", expand=True)

            # --- Controls & Indicators ---
            controls_frame = ttk.Frame(row)
            controls_frame.pack(side="left", anchor="n", padx=4)
            ttk.Button(controls_frame, text="Add Image", command=lambda i=idx: self._image_handler(i)).pack(fill="x")

            char_count_label = ttk.Label(controls_frame, text=f"{len(txt)}/{MAX_TWEET_LEN}")
            char_count_label.pack(fill="x", pady=(4, 0))
            self.char_count_labels.append(char_count_label)

            image_path_label = ttk.Label(controls_frame, text="", wraplength=120)  # Show which image is attached
            image_path_label.pack(fill="x", pady=(4, 0))
            self.image_path_labels.append(image_path_label)

        self._validate_tweets()

    def _validate_tweets(self) -> None:
        """Check all tweets for errors and update UI accordingly."""
        all_valid = True
        for i, tweet_text in enumerate(self.tweets):
            count = len(tweet_text)
            label = self.char_count_labels[i]
            label.config(text=f"{count}/{MAX_TWEET_LEN}")
            if count > MAX_TWEET_LEN or count == 0:
                label.config(style="Invalid.TLabel")
                all_valid = False
            else:
                label.config(style="Valid.TLabel")

        self.publish_btn.config(state="normal" if all_valid else "disabled")

    def _image_handler(self, index: int) -> None:
        """Prompt the user for an image and attach it to the given tweet."""
        path = filedialog.askopenfilename(
            title="Select image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")]
        )
        if path:
            self.images[index] = path
            self.image_path_labels[index].config(text=os.path.basename(path))
            messagebox.showinfo("Image attached", f"Image '{os.path.basename(path)}' added to tweet {index + 1}.")

    def _publish_handler(self) -> None:
        """Publish the composed thread using the Twitter API."""
        creds = load_twitter_credentials()
        if not all([creds.api_key, creds.api_secret, creds.access_token, creds.access_secret]):
            logging.warning("Twitter credentials not set, prompting user.")
            if not self._configure_credentials():
                messagebox.showinfo("Publish Cancelled", "Credentials were not provided.", parent=self)
                return
            creds = load_twitter_credentials()

        # If after attempting to configure, they are still not valid, then abort.
        if not all([creds.api_key, creds.api_secret, creds.access_token, creds.access_secret]):
            logging.error("Credentials still not set after configuration attempt.")
            messagebox.showerror(
                "Missing Credentials",
                "Publishing failed because credentials are still missing.",
                parent=self,
            )
            return

        try:
            self.config(cursor="watch")
            self.update_idletasks()
            publish_thread(self.tweets, self.images, creds)
            messagebox.showinfo("Success", "Thread published successfully!", parent=self)
        except Exception as exc:
            logging.exception("Failed to publish thread")
            messagebox.showerror("Error while publishing", str(exc), parent=self)
        finally:
            self.config(cursor="")


if __name__ == "__main__":
    app = ThreadComposer()
    app.mainloop()

