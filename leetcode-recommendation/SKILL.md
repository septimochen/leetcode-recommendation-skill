---
name: leetcode-recommendation
description: Refresh and analyze a user's LeetCode accepted submission history to recommend targeted new problems or reviews, and import history when requested.
---

# LeetCode practice recommendations

Use the user's accepted-submission history to identify practice patterns and recommend specific problems. History consists of JSON objects with `title`, `titleSlug`, and Unix-seconds `timestamp` as a string; each distinct problem and timestamp is an event, so repeated solves are retained.

## Import and refresh

Use `~/.config/leetcode-data/history.json` as the default history without asking for its path; honor an explicitly supplied alternative. Ask for the LeetCode.com username if needed. Do not commit personal history to a repository. Inspect the supplied export's structure and status values before importing. The helper supports JSON arrays and configurable top-level field names. For another format or nested structure, adapt it after seeing the actual export; never guess that failed submissions are accepted. Use `--accepted-only` only when the source is known to contain accepted submissions exclusively.

Before every recommendation, refresh the history. Read the LeetCode.com username from the `username` field in `~/.config/leetcode-data/config.json`, unless the user supplies a different username; ask if neither is available. Run the sync command below with that username. If refresh fails, explain that the recommendations use stale history and preserve the existing file. Do not put personal configuration in the repository.

```sh
python3 <skill-dir>/scripts/history.py import EXPORT.json
python3 <skill-dir>/scripts/history.py sync --username USERNAME
```

Run `python3 <skill-dir>/scripts/history.py import --help` for field mappings. Use `--output` on import or `--history` on sync to override the default. Import merges into an existing history. Sync requires an existing history, queries LeetCode.com for up to 20 recent accepted submissions and merges idempotently. A full response with no overlap may indicate missing records; tell the user and request a fresh full export to fill the gap. A smaller response or overlap does not prove completeness. The public API can be unavailable, return incomplete data, or change; retain existing history on failure and explain stale data. This helper targets leetcode.com, not leetcode.cn.

Use the same sync command for a manual refresh or in a user-configured daily scheduler. Creating a schedule or sending notifications requires the user's explicit request; do not set one up automatically.

## Analyze and recommend

Read the history or a faithful summary sized to the context, retaining counts, recency, repeated solves, and evidence for topic coverage. Enrich problem topics and difficulty from reliable, current problem metadata when available; do not invent tags or assume a problem's difficulty. Distinguish observed coverage and practice frequency from actual mastery: accepted records omit failed attempts, time spent, assistance, and reasoning. Ask about goals, available time, or weak areas when useful, and state meaningful uncertainty or missing history.

Recommend a practical mix of new problems and reviews suited to the user's goals and experience. For each, give the title, a LeetCode problem link (`https://leetcode.com/problems/<titleSlug>/`), the skill it practices, and a brief reason tied to the evidence. Identify reviews as previously solved and new problems as new only when the available history supports that claim; avoid implying the history is complete if it is not. Prefer verified, accessible problems and indicate uncertainty about premium access. Do not reveal solutions unless asked.

Save each set of recommendations as a Markdown file in `~/.config/leetcode-data/recommend/`, creating the directory if needed. Use a local date and time to the minute in the filename, such as `2026-11-01-1430.md`. If that filename already exists, append a suffix to avoid overwriting previous recommendations. Include the recommendations, their reasons, and relevant context or uncertainty; tell the user where the file was saved. Honor an explicitly requested alternative location. If saving fails, report the failure and still provide the recommendations.
