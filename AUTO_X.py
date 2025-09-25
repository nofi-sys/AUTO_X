"""Tkinter GUI for composing X (Twitter) threads."""

import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import List, Optional

from config import load_credentials
from plain_thread import parse_plain_thread
from twitter_api import publish_thread

logging.basicConfig(level=logging.INFO)


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
        def _check_creds() -> None:
            creds = load_credentials()
            if not all([creds.api_key, creds.api_secret, creds.access_token, creds.access_secret]):
                messagebox.showwarning(
                    "Missing Credentials",
                    "Twitter API credentials are not fully set in environment variables. "
                    "You can compose a thread, but publishing will fail.",
                )

        self.after_idle(_check_creds)

    # ───────────────────────────────────────────────────── GUI CONSTRUCTION ────
    def _build_widgets(self) -> None:
        """Create and place the GUI widgets."""
        # Input text area
        ttk.Label(self, text="Enter your full thread (blank line = manual break):").pack(anchor="w", padx=6, pady=(6, 0))
        self.input_box = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.input_box.pack(fill="x", padx=6, pady=6)

        ttk.Button(self, text="↳ Parse into Tweets", command=self._parse_handler).pack(pady=(0, 4))
        ttk.Button(self, text="🡆 Parse Plain-Thread", command=self._parse_plain_handler).pack(pady=(0, 8))

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
        creds = load_credentials()
        if not all([creds.api_key, creds.api_secret, creds.access_token, creds.access_secret]):
            messagebox.showerror(
                "Missing credentials",
                "Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_SECRET environment variables.",
            )
            logging.error("Twitter credentials not set")
            return

        try:
            publish_thread(self.tweets, self.images, creds)
            messagebox.showinfo("Success", "Thread published successfully!")
        except Exception as exc:
            logging.exception("Failed to publish thread")
            messagebox.showerror("Error while publishing", str(exc))


if __name__ == "__main__":
    app = ThreadComposer()
    app.mainloop()

