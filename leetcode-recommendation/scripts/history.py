#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "truststore>=0.10.5",
# ]
# ///
"""Normalize accepted submissions and merge a LeetCode recent-AC window."""

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

try:
    import truststore  # type: ignore[import-not-found]
except ModuleNotFoundError:
    truststore = None

if truststore is not None:
    truststore.inject_store_into_ssl()  # ensure urllib.request uses system CA bundle

QUERY = """query RecentAC($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
    title titleSlug timestamp
  }
}"""


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


def normalize_list(data, fields=FIELDS):
    if not isinstance(data, list):
        raise TypeError("expected a JSON array of submissions")
    return [normalize(item, fields) for item in data]


def merge(existing, incoming):
    result = {}
    for item in [*existing, *incoming]:
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


def fetch_recent(username):
    payload = json.dumps(
        {"query": QUERY, "variables": {"username": username, "limit": 20}}
    ).encode()
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
    if not isinstance(data, dict) or not isinstance(
        data.get("recentAcSubmissionList"), list
    ):
        raise TypeError("GraphQL response has no recent accepted submission list")
    return normalize_list(data["recentAcSubmissionList"])


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
    sync = commands.add_parser("sync", help="merge the latest 20 accepted submissions")
    sync.add_argument("--username", required=True)
    sync.add_argument("--history", default=default_history(), type=Path)
    args = parser.parse_args(argv)
    try:
        target = args.output if args.command == "import" else args.history
        if args.command == "sync" and not target.is_file():
            raise ValueError(
                f"history not found: {target}; import a history before syncing"
            )
        existing = normalize_list(read_json(target)) if target.exists() else []
        if args.command == "import":
            source = read_json(args.input)
            if not isinstance(source, list):
                raise ValueError(
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
                    item
                    for item in source
                    if item[args.status_field] == args.accepted_value
                ]
            incoming = normalize_list(
                source,
                {
                    "title": args.title_field,
                    "titleSlug": args.slug_field,
                    "timestamp": args.timestamp_field,
                },
            )
        else:
            if not args.username.strip():
                raise ValueError("username must not be empty")
            incoming = fetch_recent(args.username.strip())
            old_keys = {(item["titleSlug"], item["timestamp"]) for item in existing}
            new_keys = {(item["titleSlug"], item["timestamp"]) for item in incoming}
            if len(incoming) >= 20 and not old_keys.intersection(new_keys):
                print(
                    "Warning: full recent window has no history overlap; submissions may be missing. Import a full export to fill any gap.",
                    file=sys.stderr,
                )
        combined = merge(existing, incoming)
        write_json(target, combined)
        print(
            f"Merged {len(incoming)} accepted records; history contains {len(combined)} distinct problems."
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
