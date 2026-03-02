---
name: scout-resume
description: "Generate or improve a customized resume for a job. Use when user wants a resume tailored to a specific job posting."
argument-hint: "<job-id> [--improve] [--format pdf|docx|both]"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"os": ["darwin", "linux"], "requires": {"bins": ["scout-tools"], "anyBins": ["weasyprint"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}, {"id": "weasyprint", "kind": "brew", "formula": "weasyprint", "bins": ["weasyprint"], "label": "Install WeasyPrint for PDF generation"}]}}
---

# scout-resume

Generate or improve a customized resume for a specific job posting. Supports two modes:

- **Generate** (default): Two-pass generation — create a tailored resume, then review it for defensibility
- **Improve** (`--improve`): Three-phase improvement — generate a surgical edit plan, apply edits programmatically, then audit for credibility

See `references/two-pass-protocol.md` and `references/three-phase-protocol.md` for workflow details.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Arguments

- `<job-id>` — required, the job to generate/improve a resume for
- `--improve` — use improve mode on an existing resume instead of generating fresh
- `--format` — output format: `pdf` (default), `docx`, or `both`. Defaults to markdown-only if WeasyPrint/python-docx not installed.

---

## Prerequisite Check

### 1. Verify Analysis Exists

Check if `output/analysis/<job-id>-analysis.json` exists.

If it does NOT exist, run `/scout-analyze <job-id>` first. Analysis is required — it provides the match assessment, positioning strategy, and domain connections that guide resume tailoring.

### 2. Determine Mode

If the user specified `--improve`, go to **Improve Mode** below. Otherwise, continue with **Generate Mode**.

---

## Generate Mode (Two-Pass)

### Step 1: Load Inputs

1. Run `scout-tools data get-job --id <job-id>` — save as `JOB_DATA`
2. Read `input/base-resume.md` — the candidate's base resume (required; stop if missing)
3. Read `output/analysis/<job-id>-analysis.json` — extract the `analysis` section as `ANALYSIS`
4. Read `data/candidate-profile.json` — structured profile (use if exists)
5. Check if `data/corpus.json` exists — if so, read it for proven experience bullets (see Step 2)
6. Check if `input/additional_context.md` exists — if so, read it as supplementary factual material

### Step 2: Build Corpus Context (if corpus exists)

If `data/corpus.json` exists and has an `experiences` section:

1. Extract keywords from the job posting (title, requirements, responsibilities)
2. Find relevant bullets from the corpus by matching against skills_index and themes_index
3. Filter for bullets matching the role lens
4. Format as a "Proven Experience Bullets" section, grouped by company/role, limited to ~20 bullets
5. Include this note: "These bullets have been used in previous successful resume variations. Prefer adapting these over creating new content when they fit the job requirements."

### Step 3: Determine Role Lens

Determine the role lens from the job title and department:

- **Product** — title contains: "product manager", "product lead", "product director", "tpm", "technical product"
- **Program** — title contains: "program manager", "program lead", "program director", "tpm", "technical program"
- **Engineering** — title contains: "engineering manager", "engineer", "software", "data engineer", "analytics engineer", "director of engineering", "vp engineering", "head of engineering", "staff engineer"

If no match, check department. Default to **engineering**.

Read the matching section from `references/role-lens-guidance.md` for the determined lens and "Resume" document type.

### Step 4: Pass 1 — Generate Resume

Follow the instructions in `references/resume-generation-prompt.md`.

Construct the prompt with these sections:

```
## TARGET JOB:
<JOB_DATA as JSON>

## ROLE LENS: <ROLE_LENS uppercase>
<role lens guidance for resume from references/role-lens-guidance.md>

## PROVEN EXPERIENCE BULLETS (if corpus context was built)
<corpus context from Step 2>

## BASE RESUME (primary source material):
<contents of input/base-resume.md>

## ADDITIONAL CONTEXT (if input/additional_context.md exists):
These are real experiences the candidate has but that are NOT on the base resume.
You may draw from this material to enrich the resume, especially to address gaps
identified in the analysis. These experiences are factual and defensible.
<contents of input/additional_context.md>

## ANALYSIS & RECOMMENDATIONS:
<ANALYSIS as JSON>
```

Generate a tailored resume in Markdown format.

### Step 5: Pass 2 — Defensibility Review

**Switch to reviewer mode.** Critically evaluate the resume you just generated as if you did not write it.

Follow the instructions in `references/resume-defensibility-prompt.md`.

Review the generated resume against:

```
## TARGET JOB (for context on what might be keyword-stuffed):
<JOB_DATA as JSON>

## ORIGINAL BASE RESUME (ground truth - what the candidate actually did):
<contents of input/base-resume.md>

## ADDITIONAL CONTEXT (if exists — also valid ground truth):
Claims sourced from this material ARE real and should NOT be flagged as fabrication.
<contents of input/additional_context.md>

## TAILORED RESUME TO REVIEW:
<the resume from Pass 1>
```

Ensure every claim is defensible. Remove or tone down anything inflated, generic, or that mirrors the job description too closely. Output only the refined resume in Markdown.

### Step 6: Save and Convert

1. Build the output filename: `output/resumes/<CandidateName> Resume - <Company> - <JobTitle>.md`
   - Sanitize company and title for filename (remove special characters, limit to 50 chars each)
2. Write the final resume markdown to this file
3. Convert to the requested format:
   ```bash
   scout-tools convert resume "<md-path>" <format>
   ```
   If conversion fails (e.g., WeasyPrint not installed), inform the user that markdown was saved and PDF/DOCX requires installing WeasyPrint.

### Step 7: Update Pipeline

```bash
scout-tools pipeline advance --id <job-id> --stage resume_ready --trigger "auto:resume"
scout-tools pipeline record-artifact --id <job-id> --type resume --path "<md-path>"
```

### Step 8: Display Summary

Tell the user:
- What role lens was used
- Key positioning choices made
- File paths for markdown and any PDF/DOCX generated
- Any defensibility issues caught and corrected in Pass 2

---

## Improve Mode (Three-Phase)

### Step 1: Load Inputs

1. Run `scout-tools data get-job --id <job-id>` — save as `JOB_DATA`
2. Find the existing resume: look for `output/resumes/*<Company>*<JobTitle>*.md` matching the job
   - If no existing resume is found, tell the user to run generate mode first and stop
3. Read the existing resume as `CURRENT_RESUME`
4. Read `input/base-resume.md` as `BASE_RESUME` (required; stop if missing)
5. Read `output/analysis/<job-id>-analysis.json` — extract `analysis` section as `ANALYSIS`
   - If no analysis exists, run `/scout-analyze <job-id>` first
6. Check if `input/additional_context.md` exists — read as supplementary factual material

### Step 2: Extract Positioning Signals

From `ANALYSIS`, extract:
- `positioning_strategy` from `analysis.resume_recommendations.positioning_strategy`
- `role_archetype` from `analysis.job_summary.role_archetype`

Determine `ROLE_LENS` using the same rules as Generate Mode Step 3.

Read the matching role lens guidance from `references/role-lens-guidance.md`.

### Step 3: Phase 1 — Generate Edit Plan

Follow the instructions in `references/resume-edit-plan-prompt.md`.

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
<role lens guidance for resume>

## POSITIONING GUIDANCE FOR PROFESSIONAL SUMMARY (if positioning signals exist):
Role archetype: <role_archetype>
Positioning strategy: <positioning_strategy>
The Professional Summary should lead with the emphasis described above, NOT default to the base resume's framing.

## JOB ANALYSIS (match assessment, gaps, and recommendations):
<ANALYSIS as JSON>

## CURRENT TAILORED RESUME (the document to edit — current_text must match exactly):
<CURRENT_RESUME>

## BASE RESUME (ground truth — all facts must trace here):
<BASE_RESUME>

## ADDITIONAL CONTEXT (if exists):
These are real experiences the candidate has but that are NOT on the base resume.
They can be used as source material for "add" edits or to enrich "replace" edits.
When using this material, cite it in source_evidence as "Additional context: [relevant line]".
<contents of input/additional_context.md>
```

Request 3-8 high-impact edits. The response must be valid JSON with an `edit_plan` array. Hard cap at 8 edits — if more are returned, keep only the first 8.

Save the edit plan to `output/analysis/<job-id>-edit-plan-v<N>.json` where `<N>` is the next available version number:

```json
{
  "job_id": "<job-id>",
  "version": <N>,
  "edit_plan": <the edit plan>,
  "created_at": "<ISO 8601 timestamp>"
}
```

### Step 4: Phase 2 — Apply Edits Programmatically

Write the edit plan JSON to a temporary file, then run:

```bash
scout-tools edit apply "<resume-path>" "<edit-plan-path>"
```

This returns JSON with `resume` (the modified text), `applied` (edits that succeeded), and `failed_edits` (edits that string matching couldn't apply).

If there are `failed_edits`:
- Read each failed edit's `current_text` and `proposed_text`
- Apply these edits manually by finding the approximate location in the resume and making the replacement
- This is more reliable than string matching because you have full context of the document

Save the result as `MODIFIED_RESUME`.

### Step 5: Phase 3 — Credibility Audit

Follow the instructions in `references/resume-edit-audit-prompt.md`.

Construct the prompt:

```
## TARGET JOB (to check for parroting):
<job context — company, title, location, requirements, responsibilities>

## BASE RESUME (ground truth):
<BASE_RESUME>

## ADDITIONAL CONTEXT (if exists — also valid ground truth):
Claims sourced from this material ARE credible and should pass the credibility check.
<contents of input/additional_context.md>

## POSITIONING GUIDANCE (for Professional Summary audit, if positioning signals exist):
Role archetype: <role_archetype>
Intended positioning: <positioning_strategy>
Summary edits that align with this positioning should be passed, not softened back toward the base resume's framing.

## EDITS THAT WERE APPLIED:
<for each edit: [EDIT_TYPE] target — before/after text>

## MODIFIED RESUME (after edits):
<MODIFIED_RESUME>
```

Review ONLY the changed lines. For each edit, return one of:
- **pass** — edit is credible and natural
- **soften** — provide a revised version that fixes JD parroting, inflation, or voice mismatch
- **revert** — roll back the edit entirely

Apply any soften/revert verdicts to produce `FINAL_RESUME`.

### Step 6: Save and Convert

1. Overwrite the existing resume file with `FINAL_RESUME`
2. Convert to the requested format:
   ```bash
   scout-tools convert resume "<resume-path>" <format>
   ```

### Step 7: Update Pipeline

```bash
scout-tools pipeline advance --id <job-id> --stage resume_ready --trigger "auto:resume_improve"
scout-tools pipeline record-artifact --id <job-id> --type resume --path "<resume-path>"
```

### Step 8: Display Summary

Tell the user:
- How many edits were proposed, applied, and audited
- Which edits were softened or reverted (and why)
- File paths for markdown and any PDF/DOCX generated
- The strategic summary from the edit plan
