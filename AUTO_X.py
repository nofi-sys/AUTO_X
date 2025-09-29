"""Tkinter GUI for composing X (Twitter) threads."""

import json
import logging
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
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


class LoadThreadDialog(tk.Toplevel):
    """Dialog for selecting a thread from a loaded file."""

    def __init__(self, parent: tk.Tk, threads: List[List[str]]) -> None:  # noqa: D107
        super().__init__(parent)
        self.transient(parent)
        self.title("Select a Thread to Load")
        self.parent = parent
        self.threads = threads
        self.result: Optional[List[str]] = None

        body = ttk.Frame(self)
        self._create_widgets(body)
        body.pack(padx=20, pady=20, expand=True, fill="both")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self, master: ttk.Frame) -> None:
        """Create the tabbed view for thread selection."""
        ttk.Label(master, text="Select the thread you want to edit and post:").pack(pady=(0, 10))

        notebook = ttk.Notebook(master)
        notebook.pack(pady=5, padx=5, expand=True, fill="both")

        for i, thread in enumerate(self.threads):
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=f"Thread {i + 1}")

            text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=15, width=80)
            full_thread_text = "\n\n---\n\n".join(thread)
            text_area.insert(tk.END, full_thread_text)
            text_area.configure(state="disabled")
            text_area.pack(expand=True, fill="both")

        btn_frame = ttk.Frame(master)
        btn_frame.pack(pady=(10, 0))
        select_btn = ttk.Button(
            btn_frame, text="Load Selected Thread", command=lambda: self._select(notebook.index(notebook.select()))
        )
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
        self.opened_thread_file_path: Optional[str] = None

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

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Thread File...", command=self._open_thread_file_handler)
        menubar.add_cascade(label="File", menu=file_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Configure Credentials...", command=self._configure_credentials)
        settings_menu.add_command(label="Manage Promotions...", command=self._open_promo_manager)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # ─── Main Widgets ─────────────────────────────────────────────────────
        # Input text area
        ttk.Label(self, text="Enter your full thread (blank line = manual break):").pack(anchor="w", padx=6, pady=(6, 0))
        self.input_box = scrolledtext.ScrolledText(self, height=10, wrap=tk.WORD)
        self.input_box.pack(fill="x", padx=6, pady=6)

        # --- AI Generation Controls ---
        ai_controls_frame = ttk.LabelFrame(self, text="AI Generation Settings", padding=10)
        ai_controls_frame.pack(fill="x", padx=6, pady=4)

        # Model and Language selection
        model_lang_frame = ttk.Frame(ai_controls_frame)
        model_lang_frame.pack(fill="x", expand=True)

        ttk.Label(model_lang_frame, text="AI Model:").pack(side="left", padx=(0, 5))
        self.ai_model_var = tk.StringVar(value="gpt-4o")
        self.ai_model_menu = ttk.Combobox(
            model_lang_frame,
            textvariable=self.ai_model_var,
            values=["gpt-5", "gpt-5-mini"],
            state="readonly",
            width=15,
        )
        self.ai_model_menu.pack(side="left", padx=5)

        ttk.Label(model_lang_frame, text="Language:").pack(side="left", padx=(20, 5))
        self.language_var = tk.StringVar(value="English")
        self.language_menu = ttk.Combobox(
            model_lang_frame,
            textvariable=self.language_var,
            values=["English", "Español Rioplatense Argentino", "Other..."],
            width=25,
        )
        self.language_menu.pack(side="left", padx=5)
        self.language_menu.bind("<<ComboboxSelected>>", self._handle_language_selection)

        # Extra instructions
        ttk.Label(ai_controls_frame, text="Extra Instructions for AI:").pack(anchor="w", pady=(10, 2))
        self.extra_instructions_box = scrolledtext.ScrolledText(ai_controls_frame, height=3, wrap=tk.WORD)
        self.extra_instructions_box.pack(fill="x", expand=True, pady=(0, 5))

        # --- Action Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=(0, 8))
        ttk.Button(button_frame, text="↳ Parse into Tweets", command=self._parse_handler).pack(side="left", padx=4)
        ttk.Button(button_frame, text="🡆 Parse Plain-Thread", command=self._parse_plain_handler).pack(
            side="left", padx=4
        )
        ttk.Button(button_frame, text="✨ Generate with AI", command=self._parse_with_ai_handler).pack(
            side="left", padx=4
        )

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
    def _open_thread_file_handler(self) -> None:
        """Open a JSON file containing threads, and let the user select one to load."""
        file_path = filedialog.askopenfilename(
            title="Open Thread File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self,
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            threads = data.get("threads")
            if not isinstance(threads, list) or not all(isinstance(t, list) for t in threads):
                raise TypeError("JSON file is not in the expected format.")

            dialog = LoadThreadDialog(self, threads)
            _center_window(dialog)
            selected_thread = dialog.result

            if selected_thread:
                self.opened_thread_file_path = file_path  # Save path for later
                self._render_tweets(selected_thread)
                messagebox.showinfo("Thread Loaded", "The selected thread has been loaded into the editor.", parent=self)

        except (IOError, json.JSONDecodeError, TypeError) as e:
            messagebox.showerror("Error Loading File", f"Failed to load or parse the thread file:\n{e}", parent=self)
            self.opened_thread_file_path = None

    def _handle_language_selection(self, event: tk.Event) -> None:
        """Handle the language selection combobox."""
        if self.language_var.get() == "Other...":
            custom_language = simpledialog.askstring("Language", "Enter the language:", parent=self)
            if custom_language:
                # Add to the list of options if not already present
                current_values = list(self.language_menu["values"])
                if custom_language not in current_values:
                    self.language_menu["values"] = current_values[:-1] + [custom_language, "Other..."]
                self.language_var.set(custom_language)
            else:
                # If user cancels, revert to the first option
                self.language_var.set("English")

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
            # Get AI generation parameters from the UI
            model = self.ai_model_var.get()
            language = self.language_var.get()
            extra_instructions = self.extra_instructions_box.get("1.0", tk.END).strip()

            # Generate multiple thread versions
            threads = split_thread_with_ai(
                text=raw,
                model=model,
                language=language,
                extra_instructions=extra_instructions,
                num_versions=3,
            )
            logging.info("Generated %d thread versions with AI", len(threads))

            if not threads:
                messagebox.showerror("AI Error", "The AI returned no threads.", parent=self)
                return

            # Prompt the user to save the generated threads to a file
            file_path = filedialog.asksaveasfilename(
                title="Save Generated Threads",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                parent=self,
            )

            if not file_path:
                # User cancelled the save dialog
                messagebox.showinfo("Cancelled", "AI generation was successful, but the threads were not saved.", parent=self)
                return

            try:
                # The AI returns a list of threads. We'll save it in a JSON object
                # under a 'threads' key for clarity and future-proofing.
                data_to_save = {"threads": threads}
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                messagebox.showinfo(
                    "Success",
                    f"Successfully saved {len(threads)} generated threads to:\n{file_path}",
                    parent=self,
                )
            except IOError as e:
                messagebox.showerror("Save Error", f"Failed to save file: {e}", parent=self)

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
            preview.pack(side="top", fill="x", expand=True)
            preview.bind("<KeyRelease>", lambda event, i=idx: self._on_tweet_edited(event, i))

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

    def _on_tweet_edited(self, event: tk.Event, index: int) -> None:
        """Handle text changes in a tweet's text box."""
        if not isinstance(event.widget, tk.Text):
            return
        # Get the full content of the text box
        new_text = event.widget.get("1.0", tk.END).strip()
        # Update the internal state
        self.tweets[index] = new_text
        # Re-validate to update character count and publish button state
        self._validate_tweets()

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

            # Move the source file to "enviados" subfolder if it exists
            if self.opened_thread_file_path:
                self._archive_sent_thread_file()

        except Exception as exc:
            logging.exception("Failed to publish thread")
            messagebox.showerror("Error while publishing", str(exc), parent=self)
        finally:
            self.config(cursor="")

    def _archive_sent_thread_file(self) -> None:
        """Move the successfully posted thread's source file to an 'enviados' subfolder."""
        if not self.opened_thread_file_path:
            return

        try:
            source_path = self.opened_thread_file_path
            directory = os.path.dirname(source_path)
            filename = os.path.basename(source_path)

            archive_dir = os.path.join(directory, "enviados")
            os.makedirs(archive_dir, exist_ok=True)

            destination_path = os.path.join(archive_dir, filename)
            shutil.move(source_path, destination_path)

            logging.info(f"Archived sent thread file to {destination_path}")
            messagebox.showinfo(
                "File Archived",
                f"The source file has been moved to the 'enviados' subfolder.",
                parent=self,
            )
        except (IOError, OSError) as e:
            logging.exception(f"Could not archive sent thread file: {self.opened_thread_file_path}")
            messagebox.showerror("Archive Error", f"Could not move the source file:\n{e}", parent=self)
        finally:
            # Reset the path regardless of success to prevent re-archiving
            self.opened_thread_file_path = None


if __name__ == "__main__":
    app = ThreadComposer()
    app.mainloop()

