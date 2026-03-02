# Pipeline Stages

Application lifecycle stages in order:

```
discovered → researched → resume_ready → applied → screening → interviewing → offer → closed
```

## Stage Descriptions

| Stage | Description | Auto-Triggered By |
|-------|-------------|-------------------|
| `discovered` | Job found/imported | `scout companies`, `scout research`, job import |
| `researched` | Job analyzed | `scout analyze` |
| `resume_ready` | Resume generated | `scout resume`, `scout resume-improve` |
| `applied` | Application submitted | `scout apply` |
| `screening` | In screening process | `scout status` |
| `interviewing` | In interview rounds | `scout status` |
| `offer` | Offer received | `scout status` |
| `closed` | Final state | `scout status` with outcome |

## Closed Outcomes

When a job reaches the `closed` stage, it must have one of these outcomes:

- `accepted` — Offer accepted
- `rejected` — Application rejected by company
- `declined` — Candidate declined the opportunity
- `ghosted` — No response after reasonable time
- `withdrawn` — Candidate withdrew from process

## Stage Transitions

- `advance()` — Forward-only: new stage must be strictly ahead of current stage
- `set_status()` — Manual override: can move to any stage (forward or backward)
- `close()` — Sets status to `closed` with a required outcome
