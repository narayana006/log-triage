"""Turn a raw log line into a template by masking the parts that vary.

Two lines that differ only in timestamps, ids, addresses or numbers produce
the same template, which is what lets millions of lines collapse into a few
dozen patterns.
"""

from __future__ import annotations

import re

_TIMESTAMPS = [
    # 2024-05-01T12:00:00.123Z, 2024-05-01 12:00:00,123 +0000
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z| ?[+-]\d{2}:?\d{2}\b)?",
    # 01/May/2024:12:00:00 +0000 (access logs)
    r"\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2}(?: [+-]\d{4})?",
    # May  1 12:00:00 (syslog)
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) {1,2}\d{1,2} \d{2}:\d{2}:\d{2}",
    # 12:00:00.123
    r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b",
]

# Order matters: the most specific shapes are masked first so that the
# generic number rule at the end only sees what is left.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile("|".join(f"(?:{p})" for p in _TIMESTAMPS)), "<TS>"),
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "<UUID>",
    ),
    (re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "<EMAIL>"),
    (re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]*\d)"), "<IP>"),
    (re.compile(r"\b0[xX][0-9a-fA-F]+\b"), "<HEX>"),
    # Bare hex of 8+ characters that contains both a digit and a letter.
    (
        re.compile(r"\b(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{8,}\b"),
        "<HEX>",
    ),
    # Mixed letter/digit tokens such as request ids and pod name suffixes.
    # Requiring two digits keeps words like "http2" or "oauth2" readable.
    (
        re.compile(
            r"\b(?!\d+[A-Za-z]{1,3}\b)"  # leave "5300ms" or "512Mi" to the number rule
            r"(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d[A-Za-z0-9]*\d)[A-Za-z0-9]{5,}\b"
        ),
        "<ID>",
    ),
    # Any remaining number that does not sit inside a word ("v2" stays "v2").
    (re.compile(r"(?<![A-Za-z_\d])\d+(?:\.\d+)?"), "<NUM>"),
]

_WHITESPACE = re.compile(r"\s+")

_LEVEL = re.compile(
    r"\b(FATAL|PANIC|CRITICAL|CRIT|ERROR|ERR|WARNING|WARN|INFO|NOTICE|DEBUG|TRACE)\b",
    re.IGNORECASE,
)

_LEVEL_NAMES = {
    "FATAL": "FATAL",
    "PANIC": "FATAL",
    "CRITICAL": "FATAL",
    "CRIT": "FATAL",
    "ERROR": "ERROR",
    "ERR": "ERROR",
    "WARNING": "WARN",
    "WARN": "WARN",
    "INFO": "INFO",
    "NOTICE": "INFO",
    "DEBUG": "DEBUG",
    "TRACE": "DEBUG",
}

#: Higher is worse. Lines with no recognisable level rank with INFO.
SEVERITY = {"FATAL": 4, "ERROR": 3, "WARN": 2, "INFO": 1, "DEBUG": 0, "": 1}


def template_of(line: str) -> str:
    """Return the template for one log line."""
    text = line.strip()
    for pattern, placeholder in _RULES:
        text = pattern.sub(placeholder, text)
    return _WHITESPACE.sub(" ", text)


def level_of(line: str) -> str:
    """Return the normalised log level of a line, or "" if none is present.

    The first level keyword wins, because the level field normally comes
    before the free-text message.
    """
    match = _LEVEL.search(line)
    if not match:
        return ""
    return _LEVEL_NAMES[match.group(1).upper()]
