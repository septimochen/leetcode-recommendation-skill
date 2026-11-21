# Import LeetCode progress

## Export from LeetCode.com

This manual GraphQL request requires a logged-in LeetCode.com session. Sign in, then open your browser’s developer tools and find the `csrftoken` and `LEETCODE_SESSION` cookies for `leetcode.com`. Substitute their values locally in the request below. Keep your cookies and personal export private. This request is for manual reference only. The skill imports the saved response and uses the public recent-submission feed for refreshes.

```sh
curl --request POST \
  --url https://leetcode.com/graphql/ \
  --header 'Content-Type: application/json' \
  --header 'Cookie: csrftoken=<csrf_token>; LEETCODE_SESSION=<leetcode_session>' \
  --fail --silent --show-error \
  --output Leetcode_Progress.json \
  --data '{
    "query": "query userProgressQuestionList($filters: UserProgressQuestionListInput) { userProgressQuestionList(filters: $filters) { totalNum questions { translatedTitle frontendId title titleSlug difficulty lastSubmittedAt numSubmitted questionStatus lastResult topicTags { name nameTranslated slug } } } }",
    "operationName": "userProgressQuestionList",
    "variables": {
      "filters": {
        "skip": 0,
        "limit": 500
      }
    }
  }'
```

Keep the full JSON response. If `data.userProgressQuestionList.totalNum` exceeds the number of questions returned, set `skip` to the number already retrieved, save the next response to a new file, and repeat until you have all pages. Import each saved page.

## Import and sync

Run these commands from the repository root, using the same LeetCode account for both steps. For an installed skill, substitute its directory for `leetcode-recommendation`.

```sh
uv run leetcode-recommendation/scripts/history.py import Leetcode_Progress.json
uv run leetcode-recommendation/scripts/history.py sync --username YOUR_LEETCODE_USERNAME
```

The [sample JSON](../examples/leetcode-progress.json) shows the response envelope. The importer records rows with `questionStatus: SOLVED` and `lastResult: AC` and converts `lastSubmittedAt` to Unix seconds. A solved row whose latest submission failed is skipped because the export provides only the date of that failed submission. Sync adds individual recent submissions, including failures, and replaces matching imported acceptances with the submissions that have IDs.

To try the sample in a separate history, pass `--output /tmp/leetcode-example-history.json` to import. To sync an alternate history, pass the same file with `--history`.
