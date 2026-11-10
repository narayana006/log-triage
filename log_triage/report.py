"""Render results as text for people or JSON for programs."""

from __future__ import annotations

import json

from .analysis import Change, Comparison, Pattern, PatternSet, likely_cause


def _pattern_dict(pattern: Pattern, total: int) -> dict:
    return {
        "template": pattern.template,
        "count": pattern.count,
        "share": round(pattern.count / total, 4) if total else 0.0,
        "level": pattern.level or None,
        "first_line": pattern.first_line,
        "examples": pattern.examples,
    }


def _change_dict(change: Change, total: int) -> dict:
    data = _pattern_dict(change.pattern, total)
    data["baseline_count"] = change.baseline_count
    data["ratio"] = round(change.ratio, 2) if change.ratio is not None else None
    return data


def to_json(current: PatternSet, comparison: Comparison | None, top: int) -> str:
    total = current.total_lines
    data: dict = {
        "total_lines": total,
        "pattern_count": len(current.patterns),
        "top_patterns": [_pattern_dict(p, total) for p in current.ranked()[:top]],
    }
    if comparison is not None:
        cause = likely_cause(comparison)
        data["baseline"] = {
            "total_lines": comparison.baseline_lines,
            "pattern_count": comparison.baseline_patterns,
        }
        data["new"] = [_change_dict(c, total) for c in comparison.new]
        data["spiking"] = [_change_dict(c, total) for c in comparison.spiking]
        data["likely_cause"] = (
            {name: _change_dict(change, total) for name, change in cause.items()}
            if cause
            else None
        )
    return json.dumps(data, indent=2)


def _row(pattern: Pattern, note: str = "") -> list[str]:
    level = pattern.level or "-"
    lines = [f"{pattern.count:>8,}  {level:<5}  {pattern.template}"]
    if note:
        lines.append(f"{'':>8}         {note}")
    return lines


def _examples(pattern: Pattern, limit: int) -> list[str]:
    return [f"{'':>8}         e.g. {example}" for example in pattern.examples[:limit]]


def to_text(
    current: PatternSet,
    comparison: Comparison | None,
    top: int,
    examples: int = 1,
) -> str:
    out: list[str] = []
    header = f"{current.total_lines:,} lines -> {len(current.patterns):,} patterns"
    if comparison is not None:
        header += (
            f"  (baseline: {comparison.baseline_lines:,} lines, "
            f"{comparison.baseline_patterns:,} patterns)"
        )
    out.append(header)

    if comparison is not None:
        out.append("")
        out.append(f"NEW - not seen in baseline ({len(comparison.new)})")
        if not comparison.new:
            out.append("  none")
        for change in comparison.new[:top]:
            out.extend(_row(change.pattern))
            out.extend(_examples(change.pattern, examples))
        if len(comparison.new) > top:
            out.append(f"  ... {len(comparison.new) - top} more (raise --top to see them)")

        out.append("")
        out.append(f"SPIKING - share of lines grew vs baseline ({len(comparison.spiking)})")
        if not comparison.spiking:
            out.append("  none")
        for change in comparison.spiking[:top]:
            note = f"x{change.ratio:.1f} share of lines (baseline count {change.baseline_count:,})"
            out.extend(_row(change.pattern, note))
            out.extend(_examples(change.pattern, examples))
        if len(comparison.spiking) > top:
            out.append(f"  ... {len(comparison.spiking) - top} more (raise --top to see them)")

    out.append("")
    shown = min(top, len(current.patterns))
    out.append(f"TOP PATTERNS ({shown} of {len(current.patterns)})")
    for pattern in current.ranked()[:top]:
        out.extend(_row(pattern))

    if comparison is not None:
        out.append("")
        out.append("WHERE TO LOOK FIRST")
        cause = likely_cause(comparison)
        if cause is None:
            out.append("  No new or spiking pattern at WARN level or above.")
        else:
            earliest, loudest = cause["earliest"], cause["loudest"]
            out.append(
                f"  Earliest changed warning/error (input line {earliest.pattern.first_line:,}, "
                f"{earliest.pattern.count:,} lines):"
            )
            out.append(f"    {earliest.pattern.examples[0]}")
            if loudest.pattern is not earliest.pattern:
                out.append(
                    f"  Most frequent changed warning/error ({loudest.pattern.count:,} lines):"
                )
                out.append(f"    {loudest.pattern.examples[0]}")
            out.append("  Heuristic only: earliest is often the trigger, most frequent the symptom.")
    return "\n".join(out)
