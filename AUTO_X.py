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

    # ───────────────────────────────────────────────────── GUI CONSTRUCTION ────
    def _build_widgets(self) -> None:
        """Create and place the GUI widgets."""
        # ─── Menu Bar ─────────────────────────────────────────────────────────
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Configure Credentials...", command=self._configure_credentials)
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

        # Publish button
        self.publish_btn = ttk.Button(self, text="🚀 Publish Thread", state="disabled", command=self._publish_handler)
        self.publish_btn.pack(pady=(4, 10))

    # ───────────────────────────────────────────────────── EVENT HANDLERS ────
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
        """Use the AI splitter to generate a thread from the input text."""
        raw = self.input_box.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Nothing to generate", "Write something first!")
            return

        self.config(cursor="watch")
        self.update_idletasks()

        try:
            tweets = split_thread_with_ai(raw)
            logging.info("Generated %d tweets with AI", len(tweets))

            if not tweets:
                messagebox.showerror("AI Error", "The AI returned an empty thread.")
                return

            self._render_tweets(tweets)

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

