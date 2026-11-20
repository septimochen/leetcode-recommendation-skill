---
name: leetcode-recommendation
description: Refresh and analyze a user's LeetCode solves and recent attempts to recommend new problems, retries, or reviews, and import history when requested.
---

# LeetCode practice recommendations

Use the user's solved problems and observed submission outcomes to identify practice patterns and recommend specific problems. The accepted history is a JSON array with `title`, `titleSlug`, and a Unix-seconds `timestamp` string for the latest acceptance per problem. A separate local file holds recent attempts accumulated across refreshes.

## Import and refresh

Use `~/.config/leetcode-data/history.json` as the default history without asking for its path; honor an explicitly supplied alternative. Ask for the LeetCode.com username if needed. Do not commit personal history to a repository. Inspect the supplied export's structure and status values before importing. The helper supports JSON arrays and configurable top-level field names. For another format or nested structure, adapt it after seeing the actual export; never guess that failed submissions are accepted. Use `--accepted-only` only when the source is known to contain accepted submissions exclusively.

Before every recommendation, refresh the history. Use the username supplied by the user or the `username` field in `~/.config/leetcode-data/config.json`. Ask if neither is available. If using another account, use a separate history file. Keep the local data and configuration out of the repository.

```sh
uv run <skill-dir>/scripts/history.py import EXPORT.json
uv run <skill-dir>/scripts/history.py sync --username USERNAME
uv run <skill-dir>/scripts/history.py summary --username USERNAME
```

Run `uv run <skill-dir>/scripts/history.py import --help` for field mappings. Use `--output` on import or `--history` on sync and summary to override the default. Import merges accepted solves. Sync requires an existing history and fetches up to 20 recent submissions from LeetCode.com, including failed attempts. It saves them by submission ID in an adjacent `<history filename>.attempts.json` and merges accepted results into the existing history.

Run the local summary after syncing. If the refresh fails, use the saved data and report its age from `lastSyncedAt` when available. If the summary is unavailable, use the saved accepted history and disclose missing attempt data. If the sync warns that a full window had no overlap, mention the possible gap. Older accepted imports provide solve dates, while attempt counts cover only submissions observed through sync. Overlapping windows cannot establish complete coverage.

Use the same sync command for a manual refresh or in a user-configured daily scheduler. Creating a schedule or sending notifications requires the user's explicit request; do not set one up automatically.

## Analyze and recommend

Use `acceptedProblems` for solve coverage and `attemptsByProblem` for observed attempts, failure verdicts, and recency. Compare candidate `titleSlug` values with both. A problem with observed failures and no recorded acceptance is a candidate for a retry. Repeated failures on a solved problem, especially after its latest acceptance, can support a review. Weigh those signals alongside the user's goal, the verdicts, and recency. Attempt counts indicate submission activity. Time spent, assistance, and mastery require other evidence.

Build a shortlist with familiar problems and cached metadata. Use model knowledge to describe familiar practice patterns, and reserve claims about official tags or exact difficulty distributions for the problems with verified metadata. Read cache entries by slug with the first command below. Use the second command only for finalists whose uncertain identity, difficulty, topic, or access would affect the choice. A verification updates `~/.config/leetcode-data/problem-metadata.json` with the title, problem number, difficulty, tags, premium flag, and `verifiedAt` timestamp. If a lookup fails, use a better-known candidate or disclose the uncertainty.

```sh
uv run <skill-dir>/scripts/history.py metadata SLUG [SLUG ...]
uv run <skill-dir>/scripts/history.py metadata --verify SLUG [SLUG ...]
```

Recommend a practical mix of new problems, retries, and reviews suited to the user's goals and experience. For each, give the title, a LeetCode problem link (`https://leetcode.com/problems/<titleSlug>/`), the skill it practices, and a brief reason tied to the evidence. Describe a problem absent from both histories as new to the available record. Prefer accessible problems and indicate uncertainty about premium access. Do not reveal solutions unless asked.

Save each set of recommendations as a Markdown file in `~/.config/leetcode-data/recommend/`, creating the directory if needed. Use a local date and time to the minute in the filename, such as `2026-11-01-1430.md`. If that filename already exists, append a suffix to avoid overwriting previous recommendations. Include the recommendations, their reasons, and relevant context or uncertainty; tell the user where the file was saved. Honor an explicitly requested alternative location. If saving fails, report the failure and still provide the recommendations.
