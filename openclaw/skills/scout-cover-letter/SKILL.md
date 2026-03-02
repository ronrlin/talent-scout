---
name: scout-cover-letter
description: "Generate a tailored cover letter. Use when user wants a cover letter for a specific job."
argument-hint: "<job-id> [--format pdf|docx|both]"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"os": ["darwin", "linux"], "requires": {"bins": ["scout-tools"], "anyBins": ["weasyprint"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}, {"id": "weasyprint", "kind": "brew", "formula": "weasyprint", "bins": ["weasyprint"], "label": "Install WeasyPrint for PDF generation"}]}}
---

# scout-cover-letter

Generate a tailored cover letter using a two-pass workflow: generate, then review for specificity.

See `references/two-pass-protocol.md` for the quality rationale.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Arguments

- `<job-id>` — required, the job to generate a cover letter for
- `--format` — output format: `pdf` (default), `docx`, or `both`. Defaults to markdown-only if WeasyPrint/python-docx not installed.

---

## Steps

### 1. Load Inputs

1. Run `scout-tools data get-job --id <job-id>` — save as `JOB_DATA`. Stop if not found.
2. Read `input/base-resume.md` — the candidate's base resume (required; stop if missing)
3. Check if `output/analysis/<job-id>-analysis.json` exists — if so, read and extract the `analysis` section as `ANALYSIS`. If not, the cover letter can still be generated but will be less targeted.
4. Check if `input/additional_context.md` exists — if so, read as supplementary factual material

### 2. Determine Role Lens

Determine the role lens from the job title and department:

- **Product** — title contains: "product manager", "product lead", "product director", "tpm", "technical product"
- **Program** — title contains: "program manager", "program lead", "program director", "tpm", "technical program"
- **Engineering** — title contains: "engineering manager", "engineer", "software", "data engineer", "analytics engineer", "director of engineering", "vp engineering", "head of engineering", "staff engineer"

If no match, check department. Default to **engineering**.

Read the matching section from `references/role-lens-guidance.md` for the determined lens and "Cover Letter" document type.

### 3. Pass 1 — Generate Cover Letter

Follow the instructions in `references/cover-letter-prompt.md`.

Construct the prompt:

```
## TARGET JOB:
<JOB_DATA as JSON>

## ROLE LENS: <ROLE_LENS uppercase>
<role lens guidance for cover letter from references/role-lens-guidance.md>

## CANDIDATE RESUME:
<contents of input/base-resume.md>

## ANALYSIS (if available):
<ANALYSIS as JSON, or "No prior analysis">
```

Generate a concise cover letter following these hard constraints:

**Structure:**
- Begin with exactly ONE framing sentence — general (no company names, no job title), orienting the reader to the examples that follow
- After the opening sentence, immediately move into concrete experience
- 2-3 short paragraphs total (excluding greeting and closing)

**Content:**
- Reference the job title naturally within a sentence (not as a heading)
- Each paragraph anchored in a specific system, organizational change, or responsibility owned/led
- At least one paragraph reflects people leadership or organizational design
- Apply the role lens when selecting experiences to highlight

**Anti-patterns — do NOT:**
- Use generic motivation phrases ("I'm excited to apply," "drawn to your mission," "aligns well," "directly applicable," "ideal fit," "passionate about," "cutting-edge," "innovative")
- Paraphrase or mirror the job description or company values
- Mention years of experience, education, or personal interest in the company
- Explain *why* an experience matches — show the experience, let relevance be implicit

**Style:**
- Vary paragraph structure and sentence rhythm
- Prefer concrete actions, constraints, and outcomes over abstractions
- Confident, matter-of-fact professional tone
- No header titled "Cover Letter"
- Approximately 200-300 words total

If `input/additional_context.md` exists, incorporate those real experiences where relevant.

### 4. Pass 2 — Specificity Review

**Switch to reviewer mode.** Evaluate the cover letter as if reviewing someone else's work.

Follow the instructions in `references/cover-letter-specificity-prompt.md`.

Review the cover letter and identify any sentence that could plausibly appear in a cover letter for a DIFFERENT company without modification.

For each generic sentence:
- **REWRITE** it with specific details about the target company, role, or how the candidate's experience relates to THIS company's unique situation
- **REMOVE** it entirely if it adds no specific value

The result should read as if it could ONLY be sent to this specific company.

```
## TARGET COMPANY/ROLE:
<JOB_DATA as JSON>

## COVER LETTER TO REFINE:
<the cover letter from Pass 1>
```

Output only the refined cover letter in Markdown.

### 5. Save and Convert

1. Build the output filename: `output/cover-letters/Cover Letter - <Company> - <JobTitle>.md`
   - Sanitize company and title for filename (remove special characters, limit to 50 chars each)
2. Write the final cover letter markdown to this file
3. Convert to the requested format:
   ```bash
   scout-tools convert cover-letter "<md-path>" <format>
   ```
   If conversion fails, inform the user that markdown was saved and PDF/DOCX requires WeasyPrint.

### 6. Record Artifact

```bash
scout-tools pipeline record-artifact --id <job-id> --type cover_letter --path "<md-path>"
```

Note: Cover letter generation does NOT advance the pipeline stage (unlike resume generation).

### 7. Display Summary

Tell the user:
- What role lens was used
- File paths for markdown and any PDF/DOCX generated
- Any generic sentences caught and rewritten in Pass 2
