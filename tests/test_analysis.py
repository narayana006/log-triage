import pytest

from log_triage.analysis import collect, compare, likely_cause


def lines(template, n, start=0):
    return [template.format(i=start + i) for i in range(n)]


def test_collect_counts_and_keeps_examples():
    logs = lines("INFO request {i} ok", 5) + ["ERROR request 7 failed", "", "   "]
    result = collect(logs, max_examples=2)
    assert result.total_lines == 6  # blank lines are skipped
    ranked = result.ranked()
    assert [(p.template, p.count) for p in ranked] == [
        ("INFO request <NUM> ok", 5),
        ("ERROR request <NUM> failed", 1),
    ]
    assert ranked[0].examples == ["INFO request 0 ok", "INFO request 1 ok"]
    assert ranked[0].level == "INFO"
    assert ranked[1].first_line == 6


def test_ties_are_ranked_by_first_appearance():
    result = collect(["b happened", "a happened", "b happened", "a happened"])
    assert [p.template for p in result.ranked()] == ["b happened", "a happened"]


def test_new_patterns_are_reported_even_when_rare():
    baseline = collect(lines("INFO ok {i}", 100))
    current = collect(lines("INFO ok {i}", 100) + ["ERROR disk full on node 3"])
    result = compare(current, baseline)
    assert [c.pattern.template for c in result.new] == ["ERROR disk full on node <NUM>"]
    assert result.new[0].ratio is None
    assert result.spiking == []


def test_spike_uses_share_of_lines_not_raw_counts():
    # Ten times more traffic with the same mix is not a spike.
    baseline = collect(lines("INFO ok {i}", 90) + lines("WARN retry {i}", 10))
    current = collect(lines("INFO ok {i}", 900) + lines("WARN retry {i}", 100))
    assert compare(current, baseline).spiking == []

    # Same volume, but retries went from 10% to 50% of lines.
    current = collect(lines("INFO ok {i}", 50) + lines("WARN retry {i}", 50))
    spiking = compare(current, baseline).spiking
    assert [c.pattern.template for c in spiking] == ["WARN retry <NUM>"]
    assert spiking[0].ratio == pytest.approx(5.0)
    assert spiking[0].baseline_count == 10


def test_spike_thresholds():
    baseline = collect(lines("INFO ok {i}", 99) + ["WARN retry 1"])
    current = collect(lines("INFO ok {i}", 96) + lines("WARN retry {i}", 4))
    assert compare(current, baseline, min_count=5).spiking == []
    assert len(compare(current, baseline, min_count=4).spiking) == 1
    assert compare(current, baseline, spike_ratio=4.5, min_count=1).spiking == []
    with pytest.raises(ValueError):
        compare(current, baseline, spike_ratio=1.0)


def test_likely_cause_prefers_earliest_new_and_most_frequent():
    baseline = collect(lines("INFO ok {i}", 50) + lines("WARN retry {i}", 2))
    current = collect(
        lines("WARN retry {i}", 3)
        + lines("INFO ok {i}", 10)
        + ["WARN pool exhausted 50/50"]
        + lines("ERROR db timeout after {i}ms", 20)
        + lines("WARN retry {i}", 9)
        + ["INFO brand new but harmless"]
    )
    cause = likely_cause(compare(current, baseline))
    assert cause["earliest"].pattern.template == "WARN pool exhausted <NUM>/<NUM>"
    assert cause["loudest"].pattern.template == "ERROR db timeout after <NUM>ms"


def test_likely_cause_ignores_info_level_changes():
    baseline = collect(lines("INFO ok {i}", 10))
    current = collect(lines("INFO ok {i}", 10) + ["INFO new feature flag loaded"])
    comparison = compare(current, baseline)
    assert len(comparison.new) == 1
    assert likely_cause(comparison) is None
