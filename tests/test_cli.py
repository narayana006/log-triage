import io
import json
from pathlib import Path

import pytest

from log_triage.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def run(argv, stdin_text=""):
    out = io.StringIO()
    code = main(argv, stdin=io.StringIO(stdin_text), stdout=out)
    return code, out.getvalue()


def test_reads_stdin_without_baseline():
    code, out = run([], "INFO a 1\nINFO a 2\nERROR b\n")
    assert code == 0
    assert "3 lines -> 2 patterns" in out
    assert "INFO a <NUM>" in out
    assert "NEW" not in out


def test_example_incident_against_baseline():
    code, out = run([str(EXAMPLES / "incident.log"), "--baseline", str(EXAMPLES / "baseline.log")])
    assert code == 0
    assert "NEW - not seen in baseline (3)" in out
    assert "db: connection to <IP>:<NUM> timed out after <NUM>ms" in out
    assert "SPIKING - share of lines grew vs baseline (1)" in out
    assert "connection pool exhausted" in out.split("WHERE TO LOOK FIRST")[1]


def test_json_output(tmp_path):
    baseline = tmp_path / "base.log"
    baseline.write_text("INFO ok 1\nINFO ok 2\n")
    code, out = run(["--baseline", str(baseline), "--json"], "INFO ok 3\nERROR boom 4\n")
    assert code == 0
    data = json.loads(out)
    assert data["total_lines"] == 2
    assert data["baseline"] == {"total_lines": 2, "pattern_count": 1}
    assert [p["template"] for p in data["new"]] == ["ERROR boom <NUM>"]
    assert data["new"][0]["examples"] == ["ERROR boom 4"]
    assert data["likely_cause"]["earliest"]["template"] == "ERROR boom <NUM>"


def test_fail_on_new_exit_code(tmp_path):
    baseline = tmp_path / "base.log"
    baseline.write_text("INFO ok 1\n")
    assert run(["--baseline", str(baseline), "--fail-on-new"], "INFO ok 2\n")[0] == 0
    assert run(["--baseline", str(baseline), "--fail-on-new"], "ERROR boom\n")[0] == 1


def test_multiple_files_and_top_limit(tmp_path):
    a, b = tmp_path / "a.log", tmp_path / "b.log"
    a.write_text("alpha 1\nalpha 2\nbeta\n")
    b.write_text("alpha 3\ngamma\n")
    code, out = run([str(a), str(b), "--top", "1"])
    assert code == 0
    assert "5 lines -> 3 patterns" in out
    assert "TOP PATTERNS (1 of 3)" in out
    assert "beta" not in out


def test_empty_input_and_missing_file(capsys):
    assert run([], "\n\n")[0] == 2
    assert "no log lines" in capsys.readouterr().err
    assert run(["/nonexistent/file.log"])[0] == 2


def test_invalid_options_are_rejected():
    for argv in (["--top", "0"], ["--spike-ratio", "1"], ["--fail-on-new"]):
        with pytest.raises(SystemExit) as exc:
            run(argv, "x\n")
        assert exc.value.code == 2
