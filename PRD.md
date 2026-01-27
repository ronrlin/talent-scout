# Talent Scout - Product Requirements Document

## Overview

Talent Scout is a Python CLI tool that automates job search activities: scouting target companies, researching job openings, finding connections for outreach, and generating customized resumes and cover letters.

## Technical Stack

- **Language:** Python 3.11+
- **Interface:** Single CLI with subcommands (e.g., `scout companies`, `scout research ACME`, `scout resume JOB123`)
- **AI Provider:** Claude API (Anthropic)
- **Data Storage:** JSON files for structured data, text files for simple lists
- **PDF Generation:** Markdown to PDF (using pandoc or weasyprint)

## Target User Profile

**Geographic Preferences (Priority Order):**
1. Boca Raton, FL (in-person) - Primary target, willing to accept lower compensation
2. Palo Alto, CA (in-person) - Current location, expect premium compensation
3. Remote - Enables Boca Raton relocation, flexible on compensation

**Target Roles:**
- Engineering Manager
- Software Manager
- Technical Product Manager
- Director of Analytics Engineering

**Target Companies:**
- Public technology companies preferred
- Well-known Silicon Valley companies for Palo Alto roles
- More flexible criteria for Boca Raton opportunities
- Software must be a revenue driver, not cost center
- User will provide seed list of target/excluded companies

**Compensation Targets:**
- Base cash: $300,000/year
- Total comp (Silicon Valley): $500,000/year
- Willing to accept lower for remote or Boca Raton roles

---

## Agent Specifications

### 1. Company Scout Agent (MVP Priority)

**Purpose:** Build and prioritize lists of target companies by geographic location.

**CLI Command:**
```
scout companies [--location boca|palo|remote] [--count 15]
```

**Inputs:**
- User-provided seed list of target companies (JSON)
- User-provided exclusion list (JSON)
- Location preference
- Company count per location (default: 10-15)

**Discovery Methods:**
- Start with user-provided seed list
- Web search for companies matching criteria
- Industry databases (Crunchbase data where accessible)

**Outputs:**
- `data/companies-boca.json` - Companies with Boca Raton/South Florida presence
- `data/companies-palo.json` - Companies in Palo Alto/Bay Area
- `data/companies-remote.json` - Remote-friendly companies

**Output Schema:**
```json
{
  "companies": [
    {
      "name": "Company Name",
      "website": "https://...",
      "hq_location": "City, State",
      "industry": "...",
      "employee_count": "1000-5000",
      "public": true,
      "priority_score": 85,
      "notes": "Why this company matches criteria"
    }
  ],
  "generated_at": "2024-01-20T12:00:00Z"
}
```

---

### 2. Company Researcher Agent

**Purpose:** Deep-dive research on individual companies, including job openings.

**CLI Command:**
```
scout research <company_name> [--location boca|palo|remote]
```

**Research Areas:**
- Recent news and press releases
- Financial performance (for public companies)
- Company mission and culture
- Current job openings matching target roles

**Job Sources (Priority Order):**
1. Company career pages (most accurate)
2. LinkedIn Jobs
3. Indeed/Glassdoor

**Outputs:**
- `data/research/<company-slug>.json` - Full research dossier
- Appends to `data/jobs-{location}.json`

**Jobs Output Schema:**
```json
{
  "jobs": [
    {
      "id": "JOB-ACME-001",
      "company": "Acme Corp",
      "title": "Engineering Manager",
      "url": "https://...",
      "location": "Palo Alto, CA",
      "location_type": "palo",
      "posted_date": "2024-01-15",
      "match_score": 92,
      "match_notes": "Strong alignment with EM experience"
    }
  ]
}
```

---

### 3. Connection Finder Agent

**Purpose:** Identify potential connections at target companies for cold outreach.

**CLI Command:**
```
scout connections <company_name>
```

**Input:**
- LinkedIn profile URL (configured in `config.json`)
- Target company name

**Method:**
- Research publicly visible mutual connections
- Identify 2nd-degree connections
- Find alumni connections (school, previous companies)

**Output:**
- `data/connections/<company-slug>.json`

**Output Schema:**
```json
{
  "company": "Acme Corp",
  "connections": [
    {
      "name": "Jane Doe",
      "title": "VP Engineering",
      "connection_type": "2nd-degree",
      "mutual_connections": 3,
      "linkedin_url": "https://...",
      "outreach_priority": "high"
    }
  ]
}
```

---

### 4. Job Researcher & Resume Agent

**Purpose:** Analyze job descriptions and generate customized resumes and cover letters.

**CLI Commands:**
```
scout analyze <job_id>
scout resume <job_id>
scout cover-letter <job_id>
```

**Inputs:**
- Job ID (references job in `data/jobs-*.json`)
- Base resume (Word/Google Doc format, stored locally)
- Job description (fetched from URL or cached)

**Analysis Output:**
- Key requirements extracted
- Required vs. preferred qualifications
- Match assessment against user's experience
- Customization recommendations

**Resume Generation:**
- Parse base resume
- Reorder and emphasize relevant experience
- Adjust keywords to match job description
- Generate markdown, convert to PDF

**Output Files:**
- `output/resumes/Ron Lin Resume - {Company Name}.pdf`
- `output/cover-letters/Cover Letter {Company Name}.pdf`
- `output/analysis/{job-id}-analysis.json`

---

### 5. Cold Outreach Agent

**Purpose:** Generate professional cold outreach emails for connection requests.

**CLI Command:**
```
scout outreach <company_name> [--connection <name>]
```

**Tone:** Professional and direct - respects recipient's time while being personalized.

**Output:**
- `output/outreach/{company-slug}-{contact-name}.md`

**Email Template Structure:**
1. Brief personalized opener (shared connection, recent news, etc.)
2. Who I am (1 sentence)
3. Why this company (1 sentence)
4. Specific ask (referral, coffee chat, etc.)
5. Easy out / no pressure close

---

## Configuration

**File:** `config.json`

```json
{
  "user": {
    "name": "Ron Lin",
    "linkedin_url": "https://linkedin.com/in/...",
    "base_resume_path": "./input/base-resume.docx",
    "email": "..."
  },
  "preferences": {
    "locations": ["boca", "palo", "remote"],
    "target_roles": [
      "Engineering Manager",
      "Software Manager",
      "Technical Product Manager",
      "Director of Analytics Engineering"
    ],
    "min_company_size": 100,
    "prefer_public_companies": true
  },
  "api": {
    "anthropic_api_key": "${ANTHROPIC_API_KEY}"
  },
  "seeds": {
    "include": "./input/target-companies.json",
    "exclude": "./input/excluded-companies.json"
  }
}
```

---

## File Structure

```
talent-scout/
├── scout.py                    # Main CLI entry point
├── config.json                 # User configuration
├── agents/
│   ├── company_scout.py
│   ├── company_researcher.py
│   ├── connection_finder.py
│   ├── job_researcher.py
│   └── outreach_writer.py
├── input/
│   ├── base-resume.docx
│   ├── target-companies.json
│   └── excluded-companies.json
├── data/
│   ├── companies-boca.json
│   ├── companies-palo.json
│   ├── companies-remote.json
│   ├── jobs-boca.json
│   ├── jobs-palo.json
│   ├── jobs-remote.json
│   ├── research/
│   │   └── {company-slug}.json
│   └── connections/
│       └── {company-slug}.json
└── output/
    ├── resumes/
    │   └── Ron Lin Resume - {Company}.pdf
    ├── cover-letters/
    │   └── Cover Letter {Company}.pdf
    ├── outreach/
    │   └── {company}-{contact}.md
    └── analysis/
        └── {job-id}-analysis.json
```

---

## Implementation Phases

### Phase 1: Foundation + Company Scout (MVP)
- Project scaffolding and CLI framework
- Configuration system
- Company Scout Agent
- Basic JSON/file storage

### Phase 2: Research Pipeline
- Company Researcher Agent
- Job discovery and storage
- Web scraping infrastructure

### Phase 3: Resume Automation
- Job Researcher & Resume Agent
- Markdown to PDF pipeline
- Base resume parsing

### Phase 4: Outreach
- Connection Finder Agent
- Cold Outreach Agent
- Email template generation

---

## Success Criteria

1. Generate 10-15 prioritized target companies per location
2. Discover relevant job openings at target companies
3. Produce customized resumes that align keywords with job descriptions
4. Generate professional, personalized cold outreach emails
5. All outputs stored in organized, inspectable file structure
