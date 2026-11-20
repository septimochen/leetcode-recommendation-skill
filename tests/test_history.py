import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "leetcode-recommendation/scripts/history.py"


def load_history(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name!r} from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


history = load_history("history")


def record(slug="two-sum", timestamp="1470000000", title="Two Sum"):
    return {"title": title, "titleSlug": slug, "timestamp": timestamp}


def attempt(submission_id, status="Accepted", pending=False, **fields):
    return dict(
        record(**fields), id=submission_id, statusDisplay=status, isPending=pending
    )


def test_script_initializes_system_certificate_store(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "truststore",
        types.SimpleNamespace(inject_into_ssl=lambda: calls.append(True)),
    )
    load_history("history_with_truststore")
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
    windows = iter(
        [
            [attempt(str(i), slug=f"problem-{i}", timestamp=str(i)) for i in range(20)],
            [
                attempt(str(i), slug=f"problem-{i}", timestamp=str(i))
                for i in range(20, 40)
            ],
        ]
    )
    monkeypatch.setattr(history, "fetch_recent", lambda _: next(windows))
    command = ["sync", "--username", "alice", "--history", str(target)]
    assert history.main(command) == 0
    assert capsys.readouterr().err == ""
    assert history.main(command) == 0
    assert "no attempt overlap" in capsys.readouterr().err
    assert len(json.loads(target.read_text())) == 41


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
        history, "fetch_recent", lambda _: [attempt("1", timestamp="1470000001")]
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
    query = ["sync", "--username", "alice", "--history", str(target)]
    monkeypatch.setattr(
        history, "graphql", lambda *_: {"recentSubmissionList": [attempt("1")]}
    )
    assert history.main(query) == 0
    attempt_path = history.attempts_path(target)
    attempts_before = attempt_path.read_bytes()
    before = target.read_bytes()

    monkeypatch.setattr(
        history,
        "graphql",
        lambda *_: {"recentSubmissionList": [attempt("2"), record()]},
    )
    assert history.main(query) == 1
    assert "submission id" in capsys.readouterr().err
    assert target.read_bytes() == before
    assert attempt_path.read_bytes() == attempts_before


def test_sync_tracks_attempts_and_updates_pending_verdict(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "history.json"
    target.write_text(json.dumps([record(slug="legacy", title="Legacy")]))
    wrong_answer = attempt("1", "Wrong Answer", "Not Pending", timestamp="10")
    accepted = attempt("2", pending="Not Pending", timestamp="10")
    pending = attempt("3", None, "Pending", timestamp="20")
    final = dict(pending, statusDisplay="Time Limit Exceeded", isPending="Not Pending")
    unsolved = attempt("4", "Wrong Answer", "Not Pending", slug="unsolved")
    windows = iter(
        [[wrong_answer, accepted, pending], [accepted, final, unsolved], [pending]]
    )

    def fetch(query, variables):
        assert "recentSubmissionList" in query
        assert variables == {"username": "alice", "limit": 20}
        return {"recentSubmissionList": next(windows)}

    monkeypatch.setattr(history, "graphql", fetch)
    common = ["--username", "alice", "--history", str(target)]
    assert history.main(["sync", *common]) == 0
    initial = history.summarize_history(target, "alice")["attemptsByProblem"]["two-sum"]
    assert initial["attempts"] == 3
    assert initial["failedAttempts"] == 1
    assert history.main(["sync", *common]) == 0
    assert history.main(["sync", *common]) == 0
    capsys.readouterr()
    assert history.main(["summary", *common]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["lastSyncedAt"] > 0
    assert summary["earliestObservedAttemptAt"] == 10
    assert summary["attemptsByProblem"]["two-sum"] == {
        "title": "Two Sum",
        "attempts": 3,
        "acceptedAttempts": 1,
        "failedAttempts": 2,
        "failureStatuses": {"Wrong Answer": 1, "Time Limit Exceeded": 1},
        "latestAttemptAt": 20,
        "latestAcceptedAt": 10,
        "latestFailureAt": 20,
    }
    assert summary["attemptsByProblem"]["unsolved"]["latestAcceptedAt"] is None
    assert (
        summary["acceptedProblems"]
        == json.loads(target.read_text())
        == [
            record(slug="legacy", title="Legacy"),
            record(timestamp="10"),
        ]
    )


def test_legacy_history_has_no_observed_attempts(tmp_path):
    target = tmp_path / "history.json"
    target.write_text(json.dumps([record()]))
    assert history.summarize_history(target, "alice") == {
        "lastSyncedAt": None,
        "earliestObservedAttemptAt": None,
        "acceptedProblems": [record()],
        "attemptsByProblem": {},
    }


def test_sync_recovers_accepted_history_from_attempts(tmp_path, monkeypatch):
    target = tmp_path / "history.json"
    target.write_text("[]")
    command = ["sync", "--username", "alice", "--history", str(target)]
    monkeypatch.setattr(history, "fetch_recent", lambda _: [attempt("1")])
    write_json = history.write_json

    def interrupt_projection(path, data):
        if path == target:
            raise OSError("interrupted write")
        write_json(path, data)

    monkeypatch.setattr(history, "write_json", interrupt_projection)
    assert history.main(command) == 1
    assert json.loads(target.read_text()) == []
    assert history.summarize_history(target, "alice")["acceptedProblems"] == [record()]
    monkeypatch.setattr(history, "write_json", write_json)
    monkeypatch.setattr(history, "fetch_recent", lambda _: [])
    assert history.main(command) == 0
    assert json.loads(target.read_text()) == [record()]


def test_sync_rejects_attempts_from_another_account(tmp_path, monkeypatch, capsys):
    target = tmp_path / "history.json"
    target.write_text("[]")
    monkeypatch.setattr(history, "fetch_recent", lambda _: [attempt("1")])
    assert history.main(["sync", "--username", "alice", "--history", str(target)]) == 0
    monkeypatch.setattr(
        history, "fetch_recent", lambda _: pytest.fail("unexpected API request")
    )
    assert history.main(["sync", "--username", "bob", "--history", str(target)]) == 1
    assert "another LeetCode account" in capsys.readouterr().err


def test_metadata_reads_cache_offline_and_preserves_entries_on_failed_verification(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(history, "default_history", lambda: tmp_path / "history.json")
    path = tmp_path / "problem-metadata.json"
    question = {
        "title": "Two Sum",
        "titleSlug": "two-sum",
        "questionFrontendId": "1",
        "difficulty": "Easy",
        "isPaidOnly": False,
        "topicTags": [{"name": "Array", "slug": "array"}],
    }

    def verify(query, variables):
        assert "question(titleSlug: $slug)" in query
        assert variables == {"slug": "two-sum"}
        return {"question": question}

    monkeypatch.setattr(
        history, "graphql", lambda *_: pytest.fail("unexpected API request")
    )
    assert history.main(["metadata", "two-sum"]) == 0
    assert json.loads(capsys.readouterr().out) == {}
    assert not path.exists()
    monkeypatch.setattr(history, "graphql", verify)
    assert history.main(["metadata", "--verify", "two-sum"]) == 0
    cached = json.loads(capsys.readouterr().out)
    assert cached["two-sum"]["verifiedAt"] > 0
    assert cached == json.loads(path.read_text())

    monkeypatch.setattr(
        history, "graphql", lambda *_: pytest.fail("unexpected API request")
    )
    assert history.main(["metadata", "two-sum", "missing"]) == 0
    assert json.loads(capsys.readouterr().out) == cached

    monkeypatch.setattr(
        history, "graphql", lambda *_: {"question": dict(question, topicTags=None)}
    )
    before = path.read_bytes()
    assert history.main(["metadata", "--verify", "two-sum"]) == 1
    result = capsys.readouterr()
    assert "incomplete problem metadata" in result.err
    assert json.loads(result.out) == cached
    assert path.read_bytes() == before
