# AI-Powered X Thread Composer

This application helps you compose and publish threads on X (formerly Twitter) directly from a desktop GUI. It features a powerful AI-driven tool to automatically split long-form text into a well-structured and engaging thread.

## Features

-   **Multiple Parsing Options**:
    -   **Manual Splitting**: Write your full text and the app will automatically split it by word count, or you can use double blank lines for manual breaks.
    -   **Plain-Thread Format**: Use a simple numeric format for pre-written threads.
    -   **✨ AI-Powered Generation**: Leverage the power of OpenAI's GPT models to intelligently split your text into a coherent, ready-to-publish thread, complete with numbered tweets.
-   **Image Attachments**: Easily attach one image per tweet.
-   **Real-time Validation**: The UI provides instant feedback on character counts, preventing you from publishing tweets that are too long.
-   **Direct Publishing**: Post the entire thread to X with a single click.

## Requirements

*   Python 3.8+
*   The packages listed in `requirements.txt`

Install the requirements with:

```bash
pip install -r requirements.txt
```

## Configuration

The application loads all necessary credentials from a `.env` file in the root of the project.

1.  Create a file named `.env` in the same directory as the application.
2.  Add your API keys to the file, following the format below.

```env
# Twitter API Credentials
TWITTER_API_KEY="YOUR_TWITTER_API_KEY"
TWITTER_API_SECRET="YOUR_TWITTER_API_SECRET"
TWITTER_ACCESS_TOKEN="YOUR_TWITTER_ACCESS_TOKEN"
TWITTER_ACCESS_SECRET="YOUR_TWITTER_ACCESS_SECRET"

# OpenAI API Key for AI-powered thread generation
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

## Usage

1.  **Launch the application**:
    ```bash
    python AUTO_X.py
    ```
2.  **Write your content**: Type or paste your full text into the main text box.
3.  **Choose your method**:
    -   Click **↳ Parse into Tweets** for automatic or manual splitting.
    -   Click **🡆 Parse Plain-Thread** if you used the numeric format.
    -   Click **✨ Generate with AI** to have OpenAI structure the thread for you.
4.  **Review and edit**: The tweets will appear in a list. You can add images to each one.
5.  **Publish**: Once you're ready, click the **🚀 Publish Thread** button.