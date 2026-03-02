---
name: scout-analyze
description: "Analyze a job and assess match. Use when user wants match score, gap analysis, or resume recommendations for a specific job."
argument-hint: "<job-id>"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-analyze

Deeply analyze a job posting against the candidate's profile to produce match scores, gap analysis, domain connections, and resume recommendations.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Steps

### 1. Load Job Data

Run:
```bash
scout-tools data get-job --id <job-id>
```

If the job is not found, tell the user and stop.

Save the returned JSON as `JOB_DATA` for later steps.

### 2. Read Candidate Inputs

Read these files:
- `input/base-resume.md` — the candidate's base resume (required; stop if missing)
- `data/candidate-profile.json` — structured profile (optional, use if exists)

### 3. Check for Learned Preferences

If `data/learned-preferences.json` exists, read it and extract the `job_scoring` section (if present). Include these preferences as additional context when analyzing match quality.

### 4. Determine Role Lens

Determine the role lens from the job title and department. Use these rules:

**Product** — title contains any of: "product manager", "product lead", "product director", "tpm", "technical product"

**Program** — title contains any of: "program manager", "program lead", "program director", "tpm", "technical program"

**Engineering** — title contains any of: "engineering manager", "engineer", "software", "data engineer", "analytics engineer", "director of engineering", "vp engineering", "head of engineering", "staff engineer"

If title doesn't match, check the department field. Default to **engineering** if unclear.

Save the result as `ROLE_LENS` (one of: `engineering`, `product`, `program`).

### 5. Analyze the Job

Follow the instructions in `references/analysis-prompt.md` to produce a deep analysis.

Provide this input to the analysis:

```
## JOB POSTING:
<JOB_DATA as formatted JSON>

## CANDIDATE RESUME:
<contents of input/base-resume.md>
```

The analysis must produce a JSON result with these sections (see `references/analysis-schema.md` for the full schema):

- **job_summary** — title, company, role_archetype, business_mission, key_responsibilities, required_skills, preferred_skills, experience_required, education_required
- **match_assessment** — overall_score (0-100), strengths, gaps, transferable_skills, domain_connections
- **resume_recommendations** — positioning_strategy, skills_to_emphasize, experience_to_highlight, keywords_to_include, sections_to_adjust, language_shifts
- **cover_letter_points** — key narrative points for cover letter
- **interview_prep** — topics and examples to prepare
- **confidence_flags** — areas requiring proactive narrative control

### 6. Validate Role Archetype

The `role_archetype` field in `job_summary` must be exactly one of these values:

| Key | Description |
|-----|-------------|
| `org_leadership` | VP/Director/Head of Eng — org-wide strategy, budget, culture |
| `team_leadership` | Engineering Manager — team building, delivery, people management |
| `tech_lead` | Staff/Principal/Architect — technical direction, system design, IC with influence |
| `product` | Product Manager/TPM — roadmap, stakeholder alignment, product outcomes |
| `data` | Data/Analytics Engineering — pipelines, warehouses, BI, data platforms |
| `ml` | ML/AI Engineering — model development, MLOps, applied AI systems |
| `infra` | Platform/Infra/SRE — cloud, DevOps, reliability, infrastructure |
| `ic` | Individual Contributor — hands-on software engineering, feature delivery |

If the value doesn't match one of these keys exactly, default to `team_leadership`.

### 7. Save Analysis

Write the analysis result to `output/analysis/<job-id>-analysis.json` in this format:

```json
{
  "job_id": "<job-id>",
  "job": <JOB_DATA>,
  "analysis": <the analysis JSON from Step 5>,
  "analyzed_at": "<current ISO 8601 timestamp with timezone>"
}
```

### 8. Advance Pipeline

Run:
```bash
scout-tools pipeline advance --id <job-id> --stage researched --trigger "auto:analyze"
```

Then record the analysis artifact:
```bash
scout-tools pipeline record-artifact --id <job-id> --type analysis --path "output/analysis/<job-id>-analysis.json"
```

### 9. Display Summary

Present the analysis to the user in a readable format:

1. **Job Summary** — role title, company, archetype, business mission
2. **Match Score** — overall score with brief explanation
3. **Top Strengths** — 3-5 strongest fit areas
4. **Gaps** — real gaps with honest assessment
5. **Domain Connections** — analogous problems, shared algorithms, industry parallels
6. **Resume Recommendations** — positioning strategy and key adjustments
7. **Cover Letter Points** — narrative hooks for cover letter
8. **Interview Prep** — topics to prepare for
