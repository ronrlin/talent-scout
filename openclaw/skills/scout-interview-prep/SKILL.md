---
name: scout-interview-prep
description: "Generate interview prep talking points. Use when user has an upcoming interview or wants to prepare for a job's interview."
argument-hint: "<job-id>"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-interview-prep

Generate screening interview preparation materials with talking points, domain connection bridges, gap mitigation strategies, and anticipated questions.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Steps

### 1. Load Job Data

```bash
scout-tools data get-job --id <job-id>
```

If not found, tell the user and stop. Save as `JOB_DATA`.

### 2. Read Candidate Inputs

Read `input/base-resume.md` — the candidate's base resume (required; stop if missing).

### 3. Load Analysis

Check if `output/analysis/<job-id>-analysis.json` exists.

If it does NOT exist, run `/scout-analyze <job-id>` first. The analysis provides domain connections, strengths, and gaps that are critical for interview prep.

Read and extract the `analysis` section as `ANALYSIS`.

### 4. Determine Role Lens

Determine the role lens from the job title and department:

- **Product** — title contains: "product manager", "product lead", "product director", "tpm", "technical product"
- **Program** — title contains: "program manager", "program lead", "program director", "tpm", "technical program"
- **Engineering** — default for all other technical roles

### 5. Load Company Research (Optional)

Derive the company slug from the company name (lowercase, replace non-alphanumeric with hyphens, strip leading/trailing hyphens).

```bash
scout-tools data get-research --slug <company-slug>
```

If research exists, save it as `COMPANY_RESEARCH`. This enriches the "Why [Company]?" and "Areas to Probe" sections.

### 6. Generate Interview Prep

Follow the instructions in `references/interview-prep-prompt.md` to generate a 6-section prep document.

Construct the prompt:

```
## TARGET JOB:
Company: <company>
Title: <title>
Location: <location>
Requirements: <requirements_summary>
Responsibilities: <responsibilities_summary>
Match Notes: <match_notes>

## ROLE LENS: <ROLE_LENS uppercase>

## JOB ANALYSIS (match assessment, strengths, gaps, recommendations):
<ANALYSIS as JSON>

## DOMAIN CONNECTIONS (use these as the PRIMARY backbone for talking points):
<domain_connections from ANALYSIS, formatted as JSON>
(If none in analysis: "None provided. Generate 2-3 by analyzing the resume against job requirements.")

## CANDIDATE RESUME (ground truth — all facts must trace here):
<contents of input/base-resume.md>

## COMPANY RESEARCH (if available — use for "Why [Company]?" and "Areas to Probe"):
<COMPANY_RESEARCH as JSON, or omit section>
```

The output must be a Markdown document with exactly these 6 sections:

1. **Elevator Pitch** — 60-second self-introduction tailored to THIS role
2. **Domain Connection Talking Points** — bridge phrases, proof points, and when-to-use for each connection
3. **Strength Anchors** — concrete examples with metrics for top strengths
4. **Gap Mitigation** — honest acknowledgment, adjacent experience, 90-day plan for each gap
5. **Anticipated Questions** — talking points for: "walk me through your background", "why this role?", "why [company]?", STAR stories for top responsibilities, leadership style, questions to ask
6. **Areas to Probe** — questions to assess mutual fit around gaps/uncertainties

### 7. Save and Record

Write the prep document to:
`output/interview-prep/Interview Prep - <Company> - <JobTitle>.md`

Sanitize company and title for filename (remove special characters, limit to 50 chars each).

Record the artifact:
```bash
scout-tools pipeline record-artifact --id <job-id> --type interview_prep --path "<md-path>"
```

### 8. Display Summary

Tell the user:
- Number of sections generated
- Number of domain connection talking points
- File path for the prep document
- Key focus areas for the interview
