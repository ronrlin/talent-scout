---
name: scout-research
description: "Research a company or import a job from URL/text. Use when user mentions a company to research, shares a job URL, or pastes a job description."
argument-hint: "<company-name|url|'import'>"
allowed-tools: Read, Write, Bash, Glob, Grep, WebSearch, WebFetch
context: fork
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-research

Research a company and discover job openings, or import a job from a URL or pasted text. Auto-detects mode from the argument.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Mode Detection

Determine the mode from the user's input:

- **Company name mode** — argument is a company name (e.g., "Anthropic", "Tesla")
- **URL mode** — argument is a URL (starts with `http://` or `https://`)
- **Pasted text mode** — user pastes a job description directly

---

## Company Name Mode

### 1. Read Config

Read `config.json` for:
- `preferences.locations` — target locations
- `preferences.include_remote` — whether to include remote jobs
- `preferences.target_roles` — roles to search for (default: Engineering Manager, Software Manager, Technical Product Manager, Director of Analytics Engineering)

### 2. Check for Learned Preferences

If `data/learned-preferences.json` exists, read it and extract the `job_search` section. This will be appended to the job search prompt to improve targeting.

### 3. Research the Company

Use WebSearch and WebFetch to gather information about the company. Follow the instructions in `references/company-research-prompt.md`.

Research and compile:
- Company overview, mission, products/services
- Recent news (last 6-12 months)
- Financial health (public performance or funding status)
- Engineering culture, tech stack, practices
- Key leadership (CEO, CTO, VP Engineering)
- Office locations with engineering presence

Structure the research as JSON matching the schema in `references/company-research-prompt.md`.

### 4. Find Job Openings

Follow the instructions in `references/job-search-prompt.md` to identify current job openings at the company.

Build location type rules from config:
- For each location in `preferences.locations`, create a rule: `"<slug>" = <location description>`
- If `include_remote` is true, add: `"remote" = Remote, distributed, work from anywhere, or hybrid with remote option`
- Default rule: if location doesn't match any configured location, default to "remote" (if remote enabled) or the first configured location slug

Build target roles text from `preferences.target_roles`.

Search for jobs matching the target roles. For each job found, include:
- title, department, location, location_type (using the rules above), url (if known), posted_date, requirements_summary, match_score (0-100), match_notes

### 5. Classify Locations and Assign IDs

For each discovered job:
1. Run `scout-tools data classify-location "<job-location>"` to get the correct location_type slug
2. Generate a job ID: `JOB-<COMPANY_SLUG>-<6_HEX_CHARS>` (e.g., `JOB-ANTHROPI-A3F2B1`)
3. Set `source` to `"discovered"` and `company` to the company name

### 6. Save Results

Save the company research:
```bash
scout-tools data save-research --slug <company-slug> --json <research-json-file>
```

The research JSON should include:
```json
{
  "company": { /* company info from step 3 */ },
  "jobs": [ /* processed jobs from step 5 */ ],
  "careers_page": "URL to careers page if found",
  "search_notes": "Notes about the job search",
  "researched_at": "<ISO 8601 timestamp>"
}
```

Save each job:
```bash
scout-tools data save-job --json <job-json-file>
```

### 7. Create Pipeline Entries

For each saved job:
```bash
scout-tools pipeline create --id <job-id> --trigger "auto:research"
```

### 8. Display Summary

Present to the user:
- Company overview (2-3 sentences)
- Number of jobs found
- For each job: title, location, match score, key requirements
- Careers page URL
- Any notes about the search

---

## URL Mode

### 1. Fetch the Job Posting

Use WebFetch to retrieve the content from the URL.

If the fetch fails, inform the user and stop.

### 2. Read Config

Read `config.json` for location and role preferences (same as Company Name Mode step 1).

### 3. Check for Learned Preferences

If `data/learned-preferences.json` exists, read the `job_scoring` section for scoring context.

### 4. Parse the Job Posting

Follow the instructions in `references/job-url-parse-prompt.md` to extract structured job data.

Build location type rules and target roles text from config (same as Company Name Mode step 4).

Extract from the page content:
- company, title, department, location, location_type, posted_date
- requirements_summary, responsibilities_summary, compensation
- match_score (0-100), match_notes

### 5. Classify Location and Assign ID

1. Run `scout-tools data classify-location "<job-location>"` to get the correct location_type
2. Generate a job ID: `JOB-<COMPANY_SLUG>-<6_HEX_CHARS>`
3. Set `source` to `"imported"`, `url` to the original URL, `imported_at` to current ISO timestamp

### 6. Save and Track

```bash
scout-tools data save-job --json <job-json-file>
scout-tools pipeline create --id <job-id> --trigger "auto:import_url"
```

### 7. Display Summary

Present the parsed job details to the user:
- Company, title, location
- Match score with explanation
- Key requirements and responsibilities
- Job ID for use with other skills

---

## Pasted Text Mode

### 1. Read Config

Same as URL Mode step 2.

### 2. Check for Learned Preferences

Same as URL Mode step 3.

### 3. Parse the Job Description

Follow the instructions in `references/job-url-parse-prompt.md` to extract structured data from the pasted text.

Build location type rules and target roles text from config.

### 4. Classify Location and Assign ID

Same as URL Mode step 5, but set `source` to `"imported"` and `source_file` to `"manual"`.

### 5. Save and Track

```bash
scout-tools data save-job --json <job-json-file>
scout-tools pipeline create --id <job-id> --trigger "auto:import_markdown"
```

### 6. Display Summary

Same as URL Mode step 7.
