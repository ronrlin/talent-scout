# Scoring Criteria

How companies and jobs are scored for priority and match.

## Company Priority Score (0-100)

Used by `scout-companies` to rank scouted companies.

**Boost factors:**
- Software is a revenue driver (not just a cost center)
- Strong engineering culture / known for tech excellence
- Currently hiring for target roles
- Company size meets minimum threshold
- Public or well-funded late-stage startup (if preferred)
- Seed company (user explicitly listed it)
- Matches learned preference patterns

**Penalty factors:**
- Software is a cost center (consulting, non-tech enterprise)
- No engineering presence in target locations
- Below minimum company size
- On the exclusion list
- Matches negative learned preference patterns

## Job Match Score (0-100)

Used by `scout-research` and `scout-analyze` to score job fit.

**Boost factors:**
- Title closely matches target roles
- Requirements align with candidate's skills and experience
- Location matches configured preferences
- Company characteristics match ideal profile
- Domain connections exist between candidate experience and role
- Must-have keywords from learned preferences are present

**Penalty factors:**
- Geographic mismatch (penalize if not in preferred locations)
- Seniority mismatch (too junior or too senior)
- Title matches learned "titles to avoid" patterns
- Red flag keywords from learned preferences are present
- Requirements include skills the candidate lacks with no transferable equivalent
