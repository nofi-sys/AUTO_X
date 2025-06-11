"""Tkinter GUI for composing X (Twitter) threads."""

import logging
import tkinter as tk
logging.basicConfig(level=logging.INFO)
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import List, Optional

from config import load_credentials
from twitter_api import publish_thread


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

        self._build_widgets()

    # ───────────────────────────────────────────────────── GUI CONSTRUCTION ────
    def _build_widgets(self) -> None:
        """Create and place the GUI widgets."""
        # Input text area
        ttk.Label(self, text="Enter your full thread (blank line = manual break):").pack(anchor="w", padx=6, pady=(6, 0))
        self.input_box = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.input_box.pack(fill="x", padx=6, pady=6)

        ttk.Button(self, text="↳ Parse into Tweets", command=self._parse_handler).pack(pady=(0, 8))

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

        # Clear previous widgets
        for w in self.tweets_frame.winfo_children():
            w.destroy()

        self.tweets = tweets
        self.images = [None] * len(tweets)

        # Build tweet preview widgets
        for idx, txt in enumerate(tweets):
            row = ttk.Frame(self.tweets_frame)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=f"{idx + 1:02d}.").pack(side="left", anchor="n", padx=(0, 4))

            preview = tk.Text(row, height=min(6, (len(txt) // 50) + 1), width=70, wrap=tk.WORD)
            preview.insert("1.0", txt)
            preview.configure(state="disabled", background="#F7F7F7")
            preview.pack(side="left", fill="x", expand=True)

            ttk.Button(row, text="Add Image", command=lambda i=idx: self._image_handler(i)).pack(side="left", padx=4)

        self.publish_btn.configure(state="normal")

    def _image_handler(self, index: int) -> None:
        """Prompt the user for an image and attach it to the given tweet."""
        path = filedialog.askopenfilename(
            title="Select image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp")]
        )
        if path:
            self.images[index] = path
            messagebox.showinfo("Image attached", f"Image added to tweet {index + 1}.")

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

