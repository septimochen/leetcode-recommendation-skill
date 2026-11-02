import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "leetcode-recommendation/scripts/history.py"
spec = importlib.util.spec_from_file_location("history", SCRIPT)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def record(slug="two-sum", timestamp="1470000000", title="Two Sum"):
    return {"title": title, "titleSlug": slug, "timestamp": timestamp}


def test_script_initializes_system_certificate_store(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "truststore",
        types.SimpleNamespace(inject_into_ssl=lambda: calls.append(True)),
    )
    script_spec = importlib.util.spec_from_file_location(
        "history_with_truststore", SCRIPT
    )
    module = importlib.util.module_from_spec(script_spec)
    script_spec.loader.exec_module(module)
    assert calls == [True]


def test_import_filters_and_keeps_latest_solve_per_problem(tmp_path):
    source = tmp_path / "export.json"
    target = tmp_path / "history.json"
    source.write_text(
        json.dumps(
            [
                dict(record(), statusDisplay="Accepted"),
                dict(record(timestamp=1470000001), statusDisplay="Accepted"),
                dict(record(slug="failed"), statusDisplay="Wrong Answer"),
            ]
        )
    )
    assert history.main(["import", str(source), "--output", str(target)]) == 0
    assert history.main(["import", str(source), "--output", str(target)]) == 0
    assert json.loads(target.read_text()) == [record(timestamp="1470000001")]


def test_import_unknown_schema_does_not_damage_history(tmp_path):
    source = tmp_path / "export.json"
    target = tmp_path / "history.json"
    source.write_text(json.dumps([record()]))
    target.write_text(json.dumps([record()]))
    before = target.read_bytes()
    assert history.main(["import", str(source), "--output", str(target)]) == 1
    assert target.read_bytes() == before


def test_sync_warns_on_full_window_without_overlap(tmp_path, monkeypatch, capsys):
    target = tmp_path / "history.json"
    target.write_text(json.dumps([record()]))
    monkeypatch.setattr(
        history,
        "fetch_recent",
        lambda _: [record(slug=f"problem-{i}", timestamp=str(i)) for i in range(20)],
    )
    assert history.main(["sync", "--username", "alice", "--history", str(target)]) == 0
    assert "no history overlap" in capsys.readouterr().err
    assert len(json.loads(target.read_text())) == 21


def test_sync_failure_preserves_existing_history(tmp_path, monkeypatch):
    target = tmp_path / "history.json"
    target.write_text(json.dumps([record()]))
    before = target.read_bytes()

    def fail(_):
        raise ValueError("API error")

    monkeypatch.setattr(history, "fetch_recent", fail)
    assert history.main(["sync", "--username", "alice", "--history", str(target)]) == 1
    assert target.read_bytes() == before


def test_default_history_import_and_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    source = tmp_path / "export.json"
    source.write_text(json.dumps([record()]))
    target = tmp_path / ".config/leetcode-data/history.json"
    assert history.main(["import", str(source), "--accepted-only"]) == 0
    monkeypatch.setattr(
        history, "fetch_recent", lambda _: [record(timestamp="1470000001")]
    )
    assert history.main(["sync", "--username", "alice"]) == 0
    assert json.loads(target.read_text()) == [record(timestamp="1470000001")]


def test_merge_deduplicates_existing_and_incoming_by_latest_timestamp():
    existing = [record(timestamp="100"), record(timestamp="200")]
    incoming = [
        record(timestamp="150"),
        record(slug="other", timestamp="300", title="Other"),
    ]
    assert history.merge(existing, incoming) == [
        record(slug="other", timestamp="300", title="Other"),
        record(timestamp="200"),
    ]


def test_sync_without_history_stops_before_network(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        history, "fetch_recent", lambda _: pytest.fail("unexpected API request")
    )
    assert history.main(["sync", "--username", "alice"]) == 1
    assert not (tmp_path / ".config/leetcode-data/history.json").exists()


@pytest.mark.parametrize("value", [True, -1, "1470000000000", "2020-01-01", None])
def test_invalid_timestamps_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        history.normalize(record(timestamp=value), history.FIELDS)


def test_invalid_api_response_preserves_history(tmp_path, monkeypatch, capsys):
    target = tmp_path / "history.json"
    target.write_text(json.dumps([record()]))
    before = target.read_bytes()

    def fail(_):
        raise TypeError("GraphQL response has no recent accepted submission list")

    monkeypatch.setattr(history, "fetch_recent", fail)
    assert history.main(["sync", "--username", "alice", "--history", str(target)]) == 1
    assert "GraphQL response" in capsys.readouterr().err
    assert target.read_bytes() == before
