"""Count patterns in a log stream and compare them against a baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .templating import SEVERITY, level_of, template_of


@dataclass
class Pattern:
    """One template and what we know about the lines that matched it."""

    template: str
    count: int = 0
    level: str = ""
    first_line: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class PatternSet:
    """All patterns found in one input."""

    total_lines: int = 0
    patterns: dict[str, Pattern] = field(default_factory=dict)

    def ranked(self) -> list[Pattern]:
        """Patterns ordered by count, most frequent first."""
        return sorted(self.patterns.values(), key=lambda p: (-p.count, p.first_line))


@dataclass
class Change:
    """A pattern whose frequency differs from the baseline."""

    pattern: Pattern
    baseline_count: int
    ratio: float | None  # None for patterns that are absent from the baseline


@dataclass
class Comparison:
    new: list[Change]
    spiking: list[Change]
    baseline_lines: int
    baseline_patterns: int


def collect(lines: Iterable[str], max_examples: int = 2) -> PatternSet:
    """Template every non-blank line and count how often each template occurs."""
    result = PatternSet()
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        result.total_lines += 1
        key = template_of(line)
        pattern = result.patterns.get(key)
        if pattern is None:
            pattern = Pattern(template=key, level=level_of(line), first_line=result.total_lines)
            result.patterns[key] = pattern
        pattern.count += 1
        if len(pattern.examples) < max_examples and line not in pattern.examples:
            pattern.examples.append(line)
    return result


def compare(
    current: PatternSet,
    baseline: PatternSet,
    spike_ratio: float = 3.0,
    min_count: int = 5,
) -> Comparison:
    """Find patterns that are new or spiking relative to the baseline.

    Counts are compared as a share of all lines, so a one-hour window can be
    compared against a full day. A pattern is *spiking* when its share grew by
    at least ``spike_ratio`` and it occurs at least ``min_count`` times now.
    Every pattern absent from the baseline is *new*, whatever its count.
    """
    if spike_ratio <= 1:
        raise ValueError("spike_ratio must be greater than 1")
    new: list[Change] = []
    spiking: list[Change] = []
    for pattern in current.ranked():
        before = baseline.patterns.get(pattern.template)
        if before is None:
            new.append(Change(pattern, 0, None))
            continue
        if pattern.count < min_count:
            continue
        now_share = pattern.count / current.total_lines
        before_share = before.count / baseline.total_lines
        ratio = now_share / before_share
        if ratio >= spike_ratio:
            spiking.append(Change(pattern, before.count, ratio))
    spiking.sort(key=lambda c: (-(c.ratio or 0), -c.pattern.count))
    return Comparison(
        new=new,
        spiking=spiking,
        baseline_lines=baseline.total_lines,
        baseline_patterns=len(baseline.patterns),
    )


def likely_cause(comparison: Comparison) -> dict[str, Change] | None:
    """Pick the changed patterns most worth reading first.

    This is a heuristic, not a root-cause analysis. Among new and spiking
    patterns at WARN level or above it returns:

    * ``earliest`` - the new one that appeared first in the input, which is
      often the trigger (spiking patterns are only considered when nothing
      is new, because their first occurrence may predate the spike), and
    * ``loudest`` - the one with the most lines, which is the main symptom.

    Returns None when nothing at WARN or above changed.
    """

    def serious(changes: list[Change]) -> list[Change]:
        return [c for c in changes if SEVERITY[c.pattern.level] >= SEVERITY["WARN"]]

    new, spiking = serious(comparison.new), serious(comparison.spiking)
    suspects = new + spiking
    if not suspects:
        return None
    earliest = min(new or spiking, key=lambda c: c.pattern.first_line)
    loudest = max(
        suspects,
        key=lambda c: (c.pattern.count, SEVERITY[c.pattern.level], -c.pattern.first_line),
    )
    return {"earliest": earliest, "loudest": loudest}
