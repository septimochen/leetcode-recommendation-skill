#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "truststore>=0.10.5",
# ]
# ///
"""Track LeetCode submissions and cache verified problem metadata."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

try:
    # This dependency is declared in the standalone script metadata.
    import truststore  # ty: ignore
except ModuleNotFoundError:
    truststore = None

if truststore is not None:
    truststore.inject_into_ssl()  # ensure urllib.request uses system CA bundle

RECENT_LIMIT = 20
RECENT_QUERY = """query RecentSubmissions($username: String!, $limit: Int!) {
  recentSubmissionList(username: $username, limit: $limit) {
    id title titleSlug timestamp statusDisplay isPending
  }
}"""
METADATA_QUERY = """query ProblemMetadata($slug: String!) {
  question(titleSlug: $slug) {
    title titleSlug questionFrontendId difficulty isPaidOnly topicTags { name slug }
  }
}"""


class ProblemAttempts(TypedDict):
    title: str
    attempts: int
    acceptedAttempts: int
    failedAttempts: int
    failureStatuses: dict[str, int]
    latestAttemptAt: int
    latestAcceptedAt: int | None
    latestFailureAt: int | None


def read_json(path):
    with Path(path).open(encoding="utf-8") as source:
        return json.load(source)


def normalize(record, fields):
    if not isinstance(record, dict):
        raise TypeError("each submission must be an object")
    try:
        title = record[fields["title"]]
        slug = record[fields["titleSlug"]]
        timestamp = record[fields["timestamp"]]
    except KeyError as exc:
        raise ValueError(f"missing field: {exc.args[0]}") from exc
    if not isinstance(title, str):
        raise TypeError("title must be a string")
    if not title.strip():
        raise ValueError("title must be a nonempty string")
    if not isinstance(slug, str):
        raise TypeError("titleSlug must be a string")
    if not slug.strip():
        raise ValueError("titleSlug must be a nonempty string")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (str, int)):
        raise TypeError("timestamp must be Unix seconds")
    stamp = str(timestamp)
    if not stamp.isascii() or not stamp.isdigit() or int(stamp) > 9999999999:
        raise ValueError(
            "timestamp must be nonnegative Unix seconds (not milliseconds)"
        )
    return {
        "title": title.strip(),
        "titleSlug": slug.strip(),
        "timestamp": str(int(stamp)),
    }


FIELDS = {key: key for key in ("title", "titleSlug", "timestamp")}


def default_history():
    return Path.home() / ".config" / "leetcode-data" / "history.json"


def legacy_attempts_path(history):
    return history.with_name(f"{history.name}.attempts.json")


@contextmanager
def write_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(f"{path.name}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def normalize_list(data, fields=FIELDS):
    if not isinstance(data, list):
        raise TypeError("expected a JSON array of submissions")
    return [normalize(item, fields) for item in data]


def latest_by_problem(records):
    result = {}
    for item in records:
        slug = item["titleSlug"]
        if slug not in result or int(item["timestamp"]) > int(
            result[slug]["timestamp"]
        ):
            result[slug] = item
    return sorted(
        result.values(), key=lambda item: (-int(item["timestamp"]), item["titleSlug"])
    )


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as out:
            name = out.name
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        "https://leetcode.com/graphql/",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "leetcode-recommendation-skill/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not isinstance(result, dict) or result.get("errors"):
        raise ValueError(
            f"GraphQL request failed: {result.get('errors') if isinstance(result, dict) else 'invalid response'}"
        )
    data = result.get("data")
    if not isinstance(data, dict):
        raise TypeError("GraphQL response has no data object")
    return data


def normalize_submission(record, *, require_id):
    attempt = normalize(record, FIELDS)
    if not require_id and "id" not in record:
        if (
            record.get("statusDisplay") != "Accepted"
            or record.get("isPending", False) is not False
        ):
            raise ValueError(
                "a submission without an id must be a historical acceptance"
            )
        return dict(attempt, statusDisplay="Accepted", isPending=False)
    submission_id = record.get("id")
    if not isinstance(submission_id, str) or not submission_id.strip():
        raise ValueError("submission id must be a nonempty string")
    pending = record.get("isPending")
    if isinstance(pending, str) and pending.strip():
        # The public feed uses strings such as "Not Pending".
        pending = pending.strip().casefold() != "not pending"
    if not isinstance(pending, bool):
        raise TypeError("submission isPending must indicate judging status")
    status = record.get("statusDisplay")
    if pending and status in (None, ""):
        status = "Pending"
    if not isinstance(status, str) or not status.strip():
        raise ValueError("submission statusDisplay must be a nonempty string")
    return dict(
        attempt,
        id=submission_id.strip(),
        statusDisplay=status.strip(),
        isPending=pending,
    )


def normalize_submissions(records, *, require_id):
    if not isinstance(records, list):
        raise TypeError("expected a JSON array of submissions")
    return [normalize_submission(record, require_id=require_id) for record in records]


def fetch_recent(username):
    data = graphql(RECENT_QUERY, {"username": username, "limit": RECENT_LIMIT})
    return normalize_submissions(data.get("recentSubmissionList"), require_id=True)


def is_accepted(item):
    return not item["isPending"] and item["statusDisplay"] == "Accepted"


def acceptance_key(item):
    return item["titleSlug"], item["timestamp"]


def merge_submissions(existing, incoming):
    identified: dict[str, dict] = {}
    historical: dict[tuple[str, str], dict] = {}
    for item in [*existing, *incoming]:
        if "id" not in item:
            historical.setdefault(acceptance_key(item), item)
            continue
        previous = identified.get(item["id"])
        if previous is None or previous["isPending"] or not item["isPending"]:
            identified[item["id"]] = item
    matched = {
        acceptance_key(item) for item in identified.values() if is_accepted(item)
    }
    submissions = list(identified.values())
    submissions.extend(item for key, item in historical.items() if key not in matched)
    return sorted(
        submissions,
        key=lambda item: (
            -int(item["timestamp"]),
            item["titleSlug"],
            item.get("id", ""),
        ),
    )


def accepted_history(submissions):
    return latest_by_problem(
        normalize(item, FIELDS) for item in submissions if is_accepted(item)
    )


def normalize_history(data, *, require_id=False):
    if not isinstance(data, dict):
        raise TypeError("history must be a JSON object")
    username = data.get("username")
    if username is not None and (not isinstance(username, str) or not username.strip()):
        raise ValueError("history has an invalid LeetCode username")
    synced_at = data.get("lastSyncedAt")
    if synced_at is not None and (
        type(synced_at) is not int or synced_at < 0 or not username
    ):
        raise ValueError("history has an invalid lastSyncedAt or missing username")
    return {
        "username": username,
        "lastSyncedAt": synced_at,
        "submissions": normalize_submissions(
            data.get("submissions"), require_id=require_id
        ),
    }


def read_history(path, *, allow_missing=False):
    try:
        data = read_json(path)
    except FileNotFoundError:
        if not allow_missing:
            raise
        data = []
    if not isinstance(data, list):
        return normalize_history(data)
    try:
        state = normalize_history(
            read_json(legacy_attempts_path(path)), require_id=True
        )
    except FileNotFoundError:
        # A concurrent migration may have replaced the array before removing the sidecar.
        if path.exists():
            data = read_json(path)
            if not isinstance(data, list):
                return normalize_history(data)
        state = {"username": None, "lastSyncedAt": None, "submissions": []}
    legacy = [
        dict(item, statusDisplay="Accepted", isPending=False)
        for item in normalize_list(data)
    ]
    state["submissions"] = merge_submissions(legacy, state["submissions"])
    return state


def write_history(path, state):
    write_json(path, state)
    sidecar = legacy_attempts_path(path)
    try:
        legacy = normalize_history(read_json(sidecar), require_id=True)
        covered = {item["id"] for item in state["submissions"] if "id" in item}
        if legacy["username"] != state["username"] or any(
            item["id"] not in covered for item in legacy["submissions"]
        ):
            print(
                f"Warning: unmerged attempt history preserved at {sidecar}.",
                file=sys.stderr,
            )
        else:
            sidecar.unlink()
    except FileNotFoundError:
        pass
    except (OSError, TypeError, ValueError) as exc:
        print(
            f"Warning: could not remove the migrated attempt file: {exc}",
            file=sys.stderr,
        )


def check_username(state, username):
    stored = state["username"]
    if stored is not None and stored.casefold() != username.casefold():
        raise ValueError(
            "history belongs to another LeetCode account; use a separate history file"
        )


def import_history(args):
    source = read_json(args.input)
    if not isinstance(source, list):
        raise TypeError(
            "expected a JSON array; adapt nested exports after inspecting their schema"
        )
    if not args.accepted_only:
        if any(
            not isinstance(item, dict) or args.status_field not in item
            for item in source
        ):
            raise ValueError(
                f"every record must have {args.status_field!r}; use --accepted-only only for an accepted-only export"
            )
        source = [
            item for item in source if item[args.status_field] == args.accepted_value
        ]
    incoming = normalize_list(
        source,
        {
            "title": args.title_field,
            "titleSlug": args.slug_field,
            "timestamp": args.timestamp_field,
        },
    )
    historical = [
        dict(item, statusDisplay="Accepted", isPending=False)
        for item in latest_by_problem(incoming)
    ]
    with write_lock(args.output):
        state = read_history(args.output, allow_missing=True)
        state["submissions"] = merge_submissions(state["submissions"], historical)
        write_history(args.output, state)
    solved_count = len(accepted_history(state["submissions"]))
    print(
        f"Merged {len(incoming)} accepted records; history contains {solved_count} distinct problems."
    )


def sync_history(history, username):
    if not history.is_file():
        raise ValueError(
            f"history not found: {history}; import a history before syncing"
        )
    with write_lock(history):
        state = read_history(history)
        check_username(state, username)
        stored_ids = {item["id"] for item in state["submissions"] if "id" in item}
        incoming = fetch_recent(username)
        incoming_ids = {item["id"] for item in incoming}
        if (
            state["lastSyncedAt"] is not None
            and len(incoming_ids) == RECENT_LIMIT
            and incoming_ids.isdisjoint(stored_ids)
        ):
            print(
                "Warning: full recent window has no attempt overlap; submissions may be missing.",
                file=sys.stderr,
            )
        new_count = len(incoming_ids.difference(stored_ids))
        submissions = merge_submissions(state["submissions"], incoming)
        write_history(
            history,
            {
                "username": state["username"] or username,
                "lastSyncedAt": int(time.time()),
                "submissions": submissions,
            },
        )
    solved_count = len(accepted_history(submissions))
    print(
        f"Merged {len(incoming_ids)} recent submissions ({new_count} new); "
        f"tracking {len(stored_ids) + new_count} attempts and {solved_count} solved problems."
    )


def summarize_history(history, username):
    state = read_history(history)
    check_username(state, username)
    submissions = state["submissions"]
    attempts = [item for item in submissions if "id" in item]
    accepted = accepted_history(submissions)
    latest_acceptance = {item["titleSlug"]: int(item["timestamp"]) for item in accepted}
    attempts_by_problem: dict[str, ProblemAttempts] = {}
    for item in sorted(attempts, key=lambda item: -int(item["timestamp"])):
        slug = item["titleSlug"]
        stamp = int(item["timestamp"])
        if slug not in attempts_by_problem:
            attempts_by_problem[slug] = {
                "title": item["title"],
                "attempts": 0,
                "acceptedAttempts": 0,
                "failedAttempts": 0,
                "failureStatuses": {},
                "latestAttemptAt": stamp,
                "latestAcceptedAt": latest_acceptance.get(slug),
                "latestFailureAt": None,
            }
        stats = attempts_by_problem[slug]
        stats["attempts"] += 1
        if item["isPending"]:
            continue
        status = item["statusDisplay"]
        if status == "Accepted":
            stats["acceptedAttempts"] += 1
        else:
            stats["failedAttempts"] += 1
            failures = stats["failureStatuses"]
            failures[status] = failures.get(status, 0) + 1
            if stats["latestFailureAt"] is None:
                stats["latestFailureAt"] = stamp
    return {
        "lastSyncedAt": state["lastSyncedAt"],
        "earliestObservedAttemptAt": min(
            (int(item["timestamp"]) for item in attempts), default=None
        ),
        "acceptedProblems": accepted,
        "attemptsByProblem": attempts_by_problem,
    }


def fetch_metadata(slug):
    data = graphql(METADATA_QUERY, {"slug": slug}).get("question")
    if not isinstance(data, dict) or data.get("titleSlug") != slug:
        raise ValueError("LeetCode did not return a matching problem")
    tags = data.get("topicTags")
    if (
        not isinstance(data.get("title"), str)
        or not data["title"].strip()
        or not isinstance(data.get("questionFrontendId"), str)
        or not data["questionFrontendId"].strip()
        or data.get("difficulty") not in ("Easy", "Medium", "Hard")
        or not isinstance(data.get("isPaidOnly"), bool)
        or not isinstance(tags, list)
        or any(
            not isinstance(tag, dict)
            or not all(
                isinstance(tag.get(key), str) and tag[key].strip()
                for key in ("name", "slug")
            )
            for tag in tags
        )
    ):
        raise ValueError("LeetCode returned incomplete problem metadata")
    return {
        "title": data["title"],
        "titleSlug": slug,
        "questionFrontendId": data["questionFrontendId"],
        "difficulty": data["difficulty"],
        "isPaidOnly": data["isPaidOnly"],
        "topicTags": [{"name": tag["name"], "slug": tag["slug"]} for tag in tags],
        "verifiedAt": int(time.time()),
    }


def read_metadata_cache(path):
    try:
        cache = read_json(path)
    except FileNotFoundError:
        return {}
    if not isinstance(cache, dict):
        raise TypeError(
            "problem metadata cache must be a JSON object keyed by titleSlug"
        )
    return cache


def lookup_metadata(slugs, verify):
    slugs = list(dict.fromkeys(slugs))
    path = default_history().with_name("problem-metadata.json")
    verified = {}
    failed = False
    if verify:
        for slug in slugs:
            try:
                verified[slug] = fetch_metadata(slug)
            except (OSError, TypeError, ValueError) as exc:
                print(f"Warning: could not verify {slug}: {exc}", file=sys.stderr)
                failed = True
    if verified:
        with write_lock(path):
            cache = read_metadata_cache(path)
            cache.update(verified)
            write_json(path, cache)
    else:
        cache = read_metadata_cache(path)
    print(
        json.dumps(
            {slug: cache[slug] for slug in slugs if slug in cache}, ensure_ascii=False
        )
    )
    return int(failed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser(
        "import", help="merge a JSON export into normalized history"
    )
    importer.add_argument("input", type=Path)
    importer.add_argument("--output", default=default_history(), type=Path)
    importer.add_argument("--title-field", default="title")
    importer.add_argument("--slug-field", default="titleSlug")
    importer.add_argument("--timestamp-field", default="timestamp")
    importer.add_argument("--status-field", default="statusDisplay")
    importer.add_argument("--accepted-value", default="Accepted")
    importer.add_argument(
        "--accepted-only",
        action="store_true",
        help="input is known to contain only accepted submissions",
    )
    sync = commands.add_parser("sync", help="merge the latest 20 submissions")
    summary = commands.add_parser(
        "summary", help="summarize saved accepts and attempts"
    )
    for command in (sync, summary):
        command.add_argument("--username", required=True)
        command.add_argument("--history", default=default_history(), type=Path)
    metadata = commands.add_parser("metadata", help="read cached problem metadata")
    metadata.add_argument("slugs", metavar="SLUG", nargs="+")
    metadata.add_argument(
        "--verify",
        action="store_true",
        help="look up the listed slugs on LeetCode and update the cache",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "metadata":
            return lookup_metadata(args.slugs, args.verify)
        if args.command == "import":
            import_history(args)
        else:
            username = args.username.strip()
            if not username:
                raise ValueError("username must not be empty")
            if args.command == "sync":
                sync_history(args.history, username)
            else:
                print(
                    json.dumps(
                        summarize_history(args.history, username), ensure_ascii=False
                    )
                )
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
