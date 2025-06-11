import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location(
    "AUTO_X", Path(__file__).resolve().parents[1] / "AUTO_X.py"
)
AUTO_X = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec.loader.exec_module(AUTO_X)


def test_split_short_text():
    assert AUTO_X.split_text_into_tweets("Hello world") == ["Hello world"]


def test_split_respects_limit():
    text = "Hello " + "world " * 50
    tweets = AUTO_X.split_text_into_tweets(text, limit=50)
    assert all(len(t) <= 50 for t in tweets)
    assert "".join(tweets).replace(" ", "").startswith("Helloworld")
