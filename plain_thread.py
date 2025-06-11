import re
from typing import List

MAX_TWEET_LEN = 280


def parse_plain_thread(raw: str) -> List[str]:
    """Parse a Plain-Thread v1 string into a list of tweets.

    Parameters
    ----------
    raw : str
        Entire plain-thread text as pasted by the user.

    Returns
    -------
    List[str]
        List of tweet bodies ready for publishing.

    Raises
    ------
    ValueError
        If the format rules are not met.
    """
    # 1. Normalize newlines and trim final whitespace
    data = raw.replace("\r\n", "\n").strip() + "\n"

    # 2. Find indices with regex anchored to line start
    pattern = re.compile(r"^([0-9]+)\n\n", re.MULTILINE)
    positions = [(m.start(), int(m.group(1))) for m in pattern.finditer(data)]
    if not positions:
        raise ValueError("No se encontraron índices numéricos.")

    tweets = []
    for i, (pos, idx) in enumerate(positions):
        start = pos + len(str(idx)) + 2  # account for '\n\n'
        end = positions[i + 1][0] if i + 1 < len(positions) else len(data)
        body = data[start:end].strip()
        tweets.append((idx, body))

    # 3. Validations
    expected = list(range(1, len(tweets) + 1))
    found = [idx for idx, _ in tweets]
    if found != expected:
        raise ValueError(f"Índices fuera de orden o faltantes: {found} ≠ {expected}")
    for idx, body in tweets:
        if not body:
            raise ValueError(f"Tweet #{idx} vacío.")
        if len(body) > MAX_TWEET_LEN:
            raise ValueError(f"Tweet #{idx} supera {MAX_TWEET_LEN} caracteres.")

    # 4. Return only text bodies
    return [body for _, body in tweets]
