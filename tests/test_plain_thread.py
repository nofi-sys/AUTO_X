import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "plain_thread", Path(__file__).resolve().parents[1] / "plain_thread.py"
)
plain_thread = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plain_thread)
parse_plain_thread = plain_thread.parse_plain_thread
MAX_TWEET_LEN = plain_thread.MAX_TWEET_LEN


def test_parse_plain_thread_happy():
    raw = """1

hola

2

adios
"""
    assert parse_plain_thread(raw) == ["hola", "adios"]


def test_parse_plain_thread_bad_order():
    raw = """1

hola

3

oops
"""
    with pytest.raises(ValueError):
        parse_plain_thread(raw)


def test_parse_plain_thread_too_long():
    body = "x" * (MAX_TWEET_LEN + 1)
    raw = f"1\n\n{body}\n"
    with pytest.raises(ValueError):
        parse_plain_thread(raw)
