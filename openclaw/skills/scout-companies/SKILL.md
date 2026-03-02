---
name: scout-companies
description: "Scout and prioritize target companies for job search. Use when user wants to find companies hiring in a location."
argument-hint: "[location] [--count N]"
allowed-tools: Read, Write, Bash, Glob, Grep, WebSearch, WebFetch
context: fork
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-companies

Scout and prioritize technology companies in a target location for job search. Uses web search to discover companies, then scores and ranks them.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Arguments

- `[location]` — target location (e.g., "Palo Alto, CA", "remote", "all"). If not provided, use all locations from config.
- `[--count N]` — number of companies to find (default: from `preferences.companies_per_location` in config, typically 15-30)

## Steps

### 1. Read Config

Read `config.json` for:
- `preferences.locations` — configured locations
- `preferences.include_remote` — whether remote is included
- `preferences.target_roles` — roles to target (default: Engineering Manager, Software Manager, Technical Product Manager, Director of Analytics Engineering)
- `preferences.companies_per_location` — how many companies to find (default 15)
- `preferences.min_company_size` — minimum employee count (default 100)
- `preferences.prefer_public_companies` — whether to prefer public companies (default true)

If the user specified a location, use it. If "all", iterate over all configured locations. If not specified, use all configured locations.

### 2. Load Seed and Exclusion Lists

Check for seed companies:
- If `input/target-companies.json` exists, read it for seed company names to include
- These are companies the user is already interested in

Check for exclusion list:
- If `input/excluded-companies.json` exists, read it for companies to skip
- Filter these out of results

### 3. Check for Learned Preferences

If `data/learned-preferences.json` exists, read it and extract the `company_scout` section from `prompt_improvements`. Append this context to the scouting criteria.

### 4. Scout Companies

For each target location, follow the instructions in `references/company-scout-prompt.md`.

Use WebSearch to discover companies. Build the search based on:

**Prompt structure:**
```
Find <count> technology companies that have offices or presence in <location description>.

<seed companies section — if seed list exists>

Target roles I'm looking for:
<target roles from config>

Preferences:
- <public company preference>
- Software should be a revenue driver for the company
- Strong engineering culture is important
- Minimum ~<min_company_size> employees

<learned preferences context if available>
```

For each company found, provide:
- `name` — company name
- `website` — company URL
- `hq_location` — headquarters city, state
- `industry` — industry/sector
- `employee_count` — approximate employee count (e.g., "1000-5000")
- `public` — whether publicly traded (boolean)
- `priority_score` — 0-100 score based on fit
- `notes` — why this company is a good target

### 5. Filter and Rank

1. Remove any companies in the exclusion list (case-insensitive name match)
2. Sort by `priority_score` descending
3. Limit to the requested count

### 6. Save Results

Get the location slug:
```bash
scout-tools data classify-location "<location>"
```

Save the companies list:
```bash
scout-tools data save-companies --json <companies-json-file> --location-slug <slug> --location "<location>"
```

### 7. Display Summary

Present to the user as a ranked table:

| # | Company | Industry | Size | Score | Notes |
|---|---------|----------|------|-------|-------|
| 1 | ... | ... | ... | ... | ... |

Include:
- Total companies found
- Location searched
- Any seed companies that were included
- Suggestion to run `/scout-research <company>` for detailed research on top picks
