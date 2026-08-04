"""Progress reporting for the pipeline orchestrator.

A full build takes about an hour in the background, so it has to be possible to
see where it is without reading the log — hence the machine-readable status
file and the per-step timings that feed the next run's estimate.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("fetch_all", "scripts/fetch_all.py")
fetch_all = importlib.util.module_from_spec(_spec)
sys.modules["fetch_all"] = fetch_all
_spec.loader.exec_module(fetch_all)


@pytest.mark.parametrize("seconds, expected", [
    (0, "0s"),
    (42, "42s"),
    (59, "59s"),
    (60, "1m 00s"),
    (200, "3m 20s"),
    (3599, "59m 59s"),
    (3600, "1h 00m"),
    (5040, "1h 24m"),
])
def test_format_duration(seconds: int, expected: str) -> None:
    assert fetch_all.format_duration(seconds) == expected


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    progress = tmp_path / "progress.json"
    timings = tmp_path / "timings.json"
    monkeypatch.setattr(fetch_all, "PROGRESS_PATH", progress)
    monkeypatch.setattr(fetch_all, "TIMINGS_PATH", timings)
    return progress, timings


def _noop_script(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text("import sys\n")
    return str(path)


def test_completed_run_writes_progress_and_timings(paths, tmp_path, monkeypatch) -> None:
    progress, timings = paths
    scripts = [_noop_script(tmp_path, "a.py"), _noop_script(tmp_path, "b.py")]
    monkeypatch.setattr(fetch_all, "SCRIPTS", scripts)

    fetch_all.run(tmp_path / "db.sqlite")

    state = json.loads(progress.read_text())
    assert state["state"] == "complete"
    assert state["step"] == state["total"] == 2
    assert state["current"] is None
    assert set(json.loads(timings.read_text())) == set(scripts)


def test_failed_run_records_where_it_stopped(paths, tmp_path, monkeypatch) -> None:
    progress, _ = paths
    scripts = [_noop_script(tmp_path, "a.py"), str(tmp_path / "missing.py")]
    monkeypatch.setattr(fetch_all, "SCRIPTS", scripts)

    with pytest.raises(subprocess.CalledProcessError):
        fetch_all.run(tmp_path / "db.sqlite")

    state = json.loads(progress.read_text())
    assert state["state"] == "failed"
    assert state["step"] == 2
    assert state["current"] == "missing"


def test_timings_not_written_when_a_step_fails(paths, tmp_path, monkeypatch) -> None:
    """A partial run must not poison the next run's estimate."""
    _, timings = paths
    monkeypatch.setattr(fetch_all, "SCRIPTS", [str(tmp_path / "missing.py")])

    with pytest.raises(subprocess.CalledProcessError):
        fetch_all.run(tmp_path / "db.sqlite")

    assert not timings.exists()


def test_load_timings_tolerates_a_corrupt_file(paths, tmp_path) -> None:
    _, timings = paths
    timings.write_text("{ not json")
    assert fetch_all.load_timings() == {}


def test_league_step_is_appended_and_counted(paths, tmp_path, monkeypatch) -> None:
    progress, _ = paths
    monkeypatch.setattr(fetch_all, "SCRIPTS", [_noop_script(tmp_path, "a.py")])
    monkeypatch.setattr(fetch_all, "LEAGUE_SCRIPT", _noop_script(tmp_path, "league.py"))

    fetch_all.run(tmp_path / "db.sqlite", league="DEMONIC_PACTS")

    state = json.loads(progress.read_text())
    assert state["total"] == 2
    assert state["state"] == "complete"


def test_no_league_step_without_a_league(paths, tmp_path, monkeypatch) -> None:
    progress, _ = paths
    monkeypatch.setattr(fetch_all, "SCRIPTS", [_noop_script(tmp_path, "a.py")])
    monkeypatch.setattr(fetch_all, "LEAGUE_SCRIPT", _noop_script(tmp_path, "league.py"))

    fetch_all.run(tmp_path / "db.sqlite")
    assert json.loads(progress.read_text())["total"] == 1
