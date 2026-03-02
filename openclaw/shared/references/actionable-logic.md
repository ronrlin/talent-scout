# Actionable Logic

How the `scout-pipeline next` action dashboard groups and prioritizes items.

## Groups (in priority order)

### 1. Overdue

Applications past the follow-up deadline. Criteria:
- Pipeline status is `applied`, `screening`, or `interviewing`
- Days since last update exceeds `preferences.pipeline.follow_up_days` (default: 7)

**Action:** Follow up with the company or update status.

### 2. Ready to Act

Jobs with completed prerequisites that need the next step. Criteria:
- Status `resume_ready` — resume generated but not yet applied
- Status `researched` — analysis done, ready for resume generation

**Action:** Apply to the job or generate remaining materials.

### 3. In Progress

Active applications being tracked. Criteria:
- Status `applied`, `screening`, or `interviewing`
- Within the follow-up window (not overdue)

**Action:** Wait for response; prepare if interview stage.

### 4. Next Up

Newly discovered or researched jobs to work on. Criteria:
- Status `discovered` — needs analysis
- Sorted by match score descending

**Action:** Run analysis, then generate resume.

## Configuration

From `config.json`:
```json
{
  "preferences": {
    "pipeline": {
      "follow_up_days": 7,
      "follow_up_reminder_days": [7, 14],
      "auto_ghost_days": 30
    }
  }
}
```

- `follow_up_days` — days before a follow-up is considered overdue
- `auto_ghost_days` — days with no response before suggesting "ghosted" outcome
