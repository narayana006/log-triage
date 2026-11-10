import pytest

from log_triage.templating import level_of, template_of


@pytest.mark.parametrize(
    "line, expected",
    [
        ("2024-05-01T12:00:00.123Z started", "<TS> started"),
        ("2024-05-01 12:00:00,123 started", "<TS> started"),
        ("2024-05-01T12:00:00+05:30 started", "<TS> started"),
        ("May  1 12:00:00 host sshd[4242]: ok", "<TS> host sshd[<NUM>]: ok"),
        ('[01/May/2024:12:00:00 +0000] "GET / HTTP/1.1" 200', '[<TS>] "GET / HTTP/<NUM>" <NUM>'),
        ("req 3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b done", "req <UUID> done"),
        ("connect 10.0.3.17:5432 failed", "connect <IP>:<NUM> failed"),
        ("ptr 0xDEADBEEF freed", "ptr <HEX> freed"),
        ("commit 9fceb02d0ae598e9 deployed", "commit <HEX> deployed"),
        ("pod api-7d9f5c8b46-x2k4q ready", "pod api-<HEX>-<ID> ready"),
        ("took 5300ms using 512Mi", "took <NUM>ms using <NUM>Mi"),
        ("mail to jane.doe@example.com queued", "mail to <EMAIL> queued"),
        ("load 0.75 over 3 cores", "load <NUM> over <NUM> cores"),
    ],
)
def test_variable_parts_are_masked(line, expected):
    assert template_of(line) == expected


def test_words_with_a_single_digit_stay_readable():
    assert template_of("http2 enabled for api v2 via oauth2") == "http2 enabled for api v2 via oauth2"


def test_lines_differing_only_in_values_share_a_template():
    a = "2024-05-01T12:00:00Z ERROR db timeout after 5012ms from 10.0.0.1 user 42"
    b = "2024-05-02T03:14:15Z ERROR db timeout after 97ms from 192.168.4.200 user 9001"
    assert template_of(a) == template_of(b)


def test_different_messages_do_not_collapse():
    assert template_of("ERROR db timeout") != template_of("ERROR cache timeout")


def test_whitespace_is_normalised():
    assert template_of("  WARN \t retry   3  \n") == "WARN retry <NUM>"


@pytest.mark.parametrize(
    "line, level",
    [
        ("2024-05-01 ERROR boom", "ERROR"),
        ("level=warning msg=slow", "WARN"),
        ("[err] disk full", "ERROR"),
        ("CRITICAL out of memory", "FATAL"),
        ("INFO recovered from error", "INFO"),
        ("plain message", ""),
        ("terror and warnings ahead", ""),
    ],
)
def test_level_detection(line, level):
    assert level_of(line) == level
