# X Thread Composer

This small application lets you compose a thread for X (formerly Twitter) and publish it directly from a desktop GUI.

## Requirements

* Python 3.8+
* The packages listed in `requirements.txt`

Install the requirements with:

```bash
pip install -r requirements.txt
```

## Configuration

The app uses environment variables for the Twitter API credentials:

- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`

Set these variables before launching the application. You can export them in your shell or create a `.env` file and load it using your preferred method.

## Running

Start the GUI with:

```bash
python AUTO_X.py
```

Type your entire thread in the text box. You can separate tweets manually using a blank line, or let the app split the text automatically.

Once parsed, you can attach images to each tweet and publish the thread.

## Plain-Thread v1

The app also supports parsing a numeric format for pre-written threads. Paste text following this structure:

```
1

First tweet text

2

Second tweet text
```

Each block begins with an index line containing only digits, followed by a blank line and the tweet body. Indices must be consecutive and each body must stay within 280 characters. Use the **Parse Plain-Thread** button to load the tweets automatically.
