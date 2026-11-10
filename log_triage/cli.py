"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Iterator, Sequence

from . import __version__
from .analysis import collect, compare
from .report import to_json, to_text


def _read(paths: Sequence[str], stdin) -> Iterator[str]:
    if not paths:
        yield from stdin
        return
    for path in paths:
        if path == "-":
            yield from stdin
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            yield from handle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="log-triage",
        description="Collapse log lines into patterns and show what is new or "
        "spiking compared with a baseline.",
    )
    parser.add_argument(
        "files", nargs="*", help="log files to read ('-' for stdin); default is stdin"
    )
    parser.add_argument("-b", "--baseline", metavar="FILE", help="log file from a normal period")
    parser.add_argument("--top", type=int, default=10, help="patterns to show per section (default 10)")
    parser.add_argument(
        "--spike-ratio",
        type=float,
        default=3.0,
        help="how many times a pattern's share of lines must grow to count as spiking (default 3.0)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=5,
        help="ignore spikes in patterns with fewer lines than this (default 5)",
    )
    parser.add_argument(
        "--examples", type=int, default=1, help="example lines per new/spiking pattern (default 1)"
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument(
        "--fail-on-new",
        action="store_true",
        help="exit with status 1 if any new or spiking pattern is found (needs --baseline)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None, stdin=None, stdout=None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top < 1:
        parser.error("--top must be at least 1")
    if args.examples < 0:
        parser.error("--examples must not be negative")
    if args.spike_ratio <= 1:
        parser.error("--spike-ratio must be greater than 1")
    if args.fail_on_new and not args.baseline:
        parser.error("--fail-on-new needs --baseline")
    if not args.files and stdin.isatty():
        parser.error("no input: pass log files or pipe logs on stdin")

    keep = max(args.examples, 1)
    try:
        current = collect(_read(args.files, stdin), max_examples=keep)
        baseline = None
        if args.baseline:
            baseline = collect(_read([args.baseline], stdin), max_examples=0)
    except OSError as exc:
        print(f"log-triage: {exc}", file=sys.stderr)
        return 2

    if current.total_lines == 0:
        print("log-triage: input contained no log lines", file=sys.stderr)
        return 2
    if baseline is not None and baseline.total_lines == 0:
        print("log-triage: baseline contained no log lines", file=sys.stderr)
        return 2

    comparison = None
    if baseline is not None:
        comparison = compare(current, baseline, args.spike_ratio, args.min_count)

    if args.json:
        print(to_json(current, comparison, args.top), file=stdout)
    else:
        print(to_text(current, comparison, args.top, args.examples), file=stdout)

    if args.fail_on_new and comparison and (comparison.new or comparison.spiking):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
