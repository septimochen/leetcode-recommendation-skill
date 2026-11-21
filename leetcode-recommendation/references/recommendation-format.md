# Recommendation Markdown template

Copy the structure below into the saved note and replace the placeholders. Use the same title and section names for one problem or many.

```markdown
# LeetCode recommendations

**Generated** — <YYYY-MM-DD HH:mm (time zone)>

## Recommendations

### [<problem number>. <problem title>](https://leetcode.com/problems/<titleSlug>/)

- **Difficulty** — <Easy, Medium, Hard, or Unknown>
- **Access** — <Premium or Unverified>
- **Practice type** — <New to available history, Retry, Review, or Unknown>
- **Skill** — <practice topic>
- **Why** — <reason tied to the user's goal or observed history>
- **Budget** — <estimated practice time>

## Context

<Progress summary or session guidance when useful>

## History refresh

- **Status** — <Refreshed, Stale, or Unavailable>
- **Last successful refresh** — <YYYY-MM-DD HH:mm (time zone) or Unknown>
- **Accepted problems** — <distinct count or Unknown>
- **Notes** — <data limitations relevant to this recommendation>
```

- Repeat the problem block in suggested practice order. Use the title alone when the problem number is unknown. Include **Access** if premium access is required or uncertain, and **Budget** if a time estimate helps the user plan.
- Use **New to available history** for problems absent from both available solve and attempt records, **Retry** for observed unsuccessful attempts with no recorded solve, and **Review** for a recorded solve. Use **Unknown** when the available evidence cannot support a label.
- Include **Context** when the user asks for a review or when goals or session guidance need more space than the problem entries. Omit the section for a straightforward pick.
- Use **Refreshed** for a successful sync, **Stale** when falling back to saved history, and **Unavailable** when no history is available. In **Notes**, report why the data is stale and its age if known, a possible gap flagged by sync, or missing attempt data when relevant. Omit the field when there is nothing material to disclose.
