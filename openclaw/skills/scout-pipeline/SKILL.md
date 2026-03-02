---
name: scout-pipeline
description: "Manage job application pipeline. Use when user wants pipeline status, to record an application, update a stage, see next actions, or review all opportunities."
argument-hint: "[next|status <job-id>|apply <job-id>|pipeline|learn|jobs]"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-pipeline

Manage the job application pipeline. Supports multiple subcommands for tracking applications, recording progress, and knowing what to do next.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Subcommand Detection

Determine the subcommand from the user's input:

- **next** — "what should I do next", "next actions", "what's pending"
- **status** — "status of JOB-X", "where is JOB-X", "update JOB-X to screening"
- **apply** — "I applied to JOB-X", "record application for JOB-X"
- **pipeline** — "show pipeline", "pipeline overview", "kanban view"
- **learn** — "learn from my feedback", "analyze my preferences"
- **jobs** — "list jobs", "show all jobs", "jobs at <company>"

---

## `next` — Action Dashboard

Show the user what needs attention right now.

### Steps

1. Run:
   ```bash
   scout-tools pipeline actionable --days 7
   ```

2. The result contains 4 groups:
   - **overdue** — applications past follow-up deadline
   - **ready_to_act** — jobs with completed prerequisites (e.g., resume ready but not yet applied)
   - **in_progress** — active applications being tracked
   - **next_up** — newly discovered/researched jobs to work on

3. Present as a prioritized action list:

   **Overdue (follow up now):**
   - JOB-X at Company — applied N days ago, no response

   **Ready to Act:**
   - JOB-Y at Company — resume ready, apply now (match score: 85)

   **In Progress:**
   - JOB-Z at Company — screening stage, applied N days ago

   **Next Up:**
   - JOB-W at Company — discovered, needs analysis (match score: 90)

4. For each group, suggest the appropriate next action (e.g., "run `/scout-resume JOB-X`" or "follow up on your application").

---

## `status` — View or Update Pipeline Status

### View Status

If the user asks about a job's status without specifying a new stage:

```bash
scout-tools pipeline get --id <job-id>
```

Display the current stage, timestamps, history, artifacts, and notes.

### Update Status

If the user wants to change the stage (e.g., "move JOB-X to screening"):

Valid stages (see `references/pipeline-stages.md`):
```
discovered → researched → resume_ready → applied → screening → interviewing → offer → closed
```

```bash
scout-tools pipeline set-status --id <job-id> --stage <stage> --trigger "manual:status"
```

### Close with Outcome

If the user wants to close an application (e.g., "I got rejected from JOB-X"):

Valid outcomes: `accepted`, `rejected`, `declined`, `ghosted`, `withdrawn`

```bash
scout-tools pipeline close --id <job-id> --outcome <outcome> --trigger "manual:status"
```

### Add Notes

If the user wants to add a note:

```bash
scout-tools pipeline add-note --id <job-id> --note "<note text>"
```

---

## `apply` — Record an Application

When the user has applied to a job:

### Steps

1. Get the job to confirm it exists:
   ```bash
   scout-tools data get-job --id <job-id>
   ```

2. Advance to the `applied` stage:
   ```bash
   scout-tools pipeline set-status --id <job-id> --stage applied --trigger "manual:apply"
   ```

3. If the user provided details (method, notes, date), add a note:
   ```bash
   scout-tools pipeline add-note --id <job-id> --note "Applied via <method> on <date>. <notes>"
   ```

4. Confirm the application was recorded and suggest next steps (e.g., "set a follow-up reminder in 7 days").

---

## `pipeline` — Pipeline Overview

Show a kanban-style view of all tracked applications.

### Steps

1. Run:
   ```bash
   scout-tools pipeline overview
   ```

2. Also get stats:
   ```bash
   scout-tools pipeline get-stats
   ```

3. Display as a stage-by-stage breakdown:

   ```
   Pipeline Overview (N total)

   discovered (X)     → JOB-A Company - Title (score: 85)
   researched (X)     → JOB-B Company - Title (score: 90)
   resume_ready (X)   → JOB-C Company - Title (score: 78)
   applied (X)        → JOB-D Company - Title (applied 5d ago)
   screening (X)      → JOB-E Company - Title
   interviewing (X)   →
   offer (X)          →
   closed (X)         → JOB-F Company - Title (rejected)
   ```

4. Include conversion stats if available (e.g., "applied→screening: 60%").

If the user specified a stage filter (e.g., "show pipeline at applied"), filter to just that stage.

---

## `learn` — Analyze Feedback and Learn Preferences

Analyze imported and deleted jobs to improve future targeting.

### Steps

1. Get imported jobs (positive signals):
   ```bash
   scout-tools data list-jobs --source imported
   ```

2. Get deleted jobs (negative signals):
   ```bash
   scout-tools data get-deleted-jobs
   ```

3. If neither exists, tell the user: "No feedback to learn from yet. Import jobs you like or delete jobs you don't want to generate targeting improvements."

4. Analyze both sets together to identify:
   - **Positive patterns** — title patterns, key skills, industries, company traits from imported jobs
   - **Negative patterns** — titles to avoid, role red flags, company characteristics to deprioritize from deleted jobs
   - **Improved targeting** — primary titles to search, must-have keywords, red flag keywords, ideal company profile
   - **Scoring adjustments** — boost factors and penalty factors for match scoring

   Use the learning prompts from `references/learning-prompts.md` to structure the analysis.

5. Save the learned preferences:
   ```bash
   scout-tools data save-learned-prefs --json <preferences-json-file>
   ```

   The preferences JSON should include:
   ```json
   {
     "generated_at": "<ISO timestamp>",
     "based_on_imported": <count>,
     "based_on_deleted": <count>,
     "imported_job_ids": ["..."],
     "deleted_job_ids": ["..."],
     "positive_analysis": { /* patterns from imported jobs */ },
     "negative_analysis": { /* patterns from deleted jobs */ },
     "improved_targeting": { /* refined search criteria */ },
     "scoring_adjustments": { /* boost and penalty factors */ },
     "prompt_improvements": { /* text to inject into future prompts */ },
     "insights": "2-3 sentence summary"
   }
   ```

6. Display the insights and key targeting changes to the user.

---

## `jobs` — List Jobs

List all tracked jobs with optional filtering.

### Steps

1. Run with appropriate filters:
   ```bash
   scout-tools data list-jobs [--location <location>] [--company <company>] [--source <source>]
   ```

2. Get pipeline data for stage information:
   ```bash
   scout-tools pipeline get-all
   ```

3. Present as a sorted table (by match score descending):

   | Job ID | Company | Title | Location | Score | Stage |
   |--------|---------|-------|----------|-------|-------|
   | JOB-X  | ...     | ...   | ...      | 85    | researched |

4. If the user specified a stage filter, only show jobs at that stage.
