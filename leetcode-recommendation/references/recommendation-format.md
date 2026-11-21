# LeetCode practice note Markdown template

Use the shared title and timestamp, then add the sections that answer the request. Lead with what the user asked for and keep the level of detail proportional to the task. Use the section names below where they fit, and add a specific level-two heading when a new kind of request needs one. Leave out unused sections and fields.

## Title and timestamp

```markdown
# LeetCode — <title that describes the request>

**Generated** — <YYYY-MM-DD HH:mm (time zone)>
```

For example, use **Recent progress**, **Weekly practice plan**, or **Relaxed pick** as the title after `LeetCode —`.

## Progress review

```markdown
## Recent progress

**Period** — <start date to end date>

<Summary of recorded activity, with dated examples>

## Strengths

- **<Skill or topic>** — <specific evidence and what it supports>

## Growth areas

- **<Skill or topic>** — <observed difficulty or gap in coverage and the evidence for it>
```

Use the requested period or state the date range you chose. For period-specific counts, filter the underlying submissions by timestamp and distinguish distinct problems with a recorded acceptance from observed submission attempts. Use dated solves for evidence of coverage and verdicts for observed difficulty. Distinguish repeated difficulty from sparse coverage, and say when the evidence is too limited to assess a strength or weakness. Add a follow-up plan or picks when the user asks for them.

## Practice plan

```markdown
## Practice plan

**Period** — <start date to end date, or a relative span for an undated plan>

**Goal** — <what the user will practice>

### <Day or session>

- <task, skill focus, and reason for this session>
```

Repeat the session block as needed. Use dates when the user asks for a calendar week, and use numbered sessions when timing is flexible. Match the workload to the user's availability and state important assumptions. Keep assigned problems in their sessions and use the compact line below. Add time budgets, review sessions, rest, or a checkpoint when they help the user follow the plan.

```markdown
- [<problem number>. <problem title>](https://leetcode.com/problems/<titleSlug>/) — <difficulty> · <practice type>. <Skill focus and reason>
```

## Problem picks

```markdown
## Recommendations

### [<problem number>. <problem title>](https://leetcode.com/problems/<titleSlug>/)

- **Difficulty** — <Easy, Medium, Hard, or Unknown>
- **Practice type** — <New to available history, Retry, Review, or Unknown>
- **Skill** — <practice topic>
- **Why** — <reason tied to the user's goal or observed history>
- **Access** — <Premium or Unverified>
- **Budget** — <estimated practice time>
```

Use one short entry for a single relaxed Easy pick. For a shortlist, repeat the block in suggested practice order. Use the title alone when the problem number is unknown. Include **Access** if premium access is required or uncertain, and **Budget** if a time estimate helps.

Use **New to available history** for problems absent from both available solve and attempt records, **Retry** for observed unsuccessful attempts with no recorded solve, and **Review** for a recorded solve. Use **Unknown** when the available evidence cannot support a label.

## History refresh

End the note with this block if history informed the result or a refresh was attempted.

```markdown
## History refresh

- **Status** — <Refreshed, Stale, Saved history, or Unavailable>
- **Last successful refresh** — <YYYY-MM-DD HH:mm (time zone) or Unknown>
- **Accepted problems** — <distinct count or Unknown>
- **Notes** — <data limitations relevant to the note>
```

Use **Refreshed** for a successful sync, **Stale** when falling back to saved history after a failed sync, **Saved history** when the user asked to work from the saved data, and **Unavailable** when no history is available. Report the distinct accepted count for the available history. In **Notes**, include material limits such as the reason the data is stale and its age if known, a gap flagged by sync, or missing attempt coverage. Omit **Notes** when there is nothing material to disclose.
