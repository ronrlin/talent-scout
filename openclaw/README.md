# Talent Scout — OpenClaw Skills

AI-powered job search automation as 8 composable OpenClaw skills.

## Quick Install

```bash
clawhub install talent-scout
```

This installs all 8 skills and the `scout-tools` CLI dependency.

To install individual skills:

```bash
clawhub install talent-scout/scout-resume
```

## Prerequisites

- Python 3.11+
- [OpenClaw](https://openclaw.dev) CLI
- Anthropic API key (`ANTHROPIC_API_KEY` environment variable)
- WeasyPrint (optional, for PDF output): `brew install weasyprint`

## First-Run Setup

1. **Install the skills** (see above)
2. **Run setup** to create config and parse your resume:
   ```
   /scout-setup
   ```
   This will:
   - Create `config.json` with your location preferences and target roles
   - Parse `input/base-resume.md` into a structured candidate profile
   - Verify directory structure

3. **Add your base resume** at `input/base-resume.md` (standard markdown format)

4. **Optionally add seed companies** at `input/target-companies.json`:
   ```json
   [{"name": "Company Name", "reason": "Why you're interested"}]
   ```

## Workflow

The typical workflow follows this progression:

```
scout-companies → scout-research → scout-analyze → scout-resume → scout-cover-letter
         └──────────────────── scout-pipeline (track everything) ────────────────────┘
```

### 1. Scout companies

Find companies hiring in your target locations:

```
/scout-companies Palo Alto, CA
```

### 2. Research a company

Deep-dive on a company — find open jobs, culture, leadership:

```
/scout-research Stripe
```

Or import a specific job from a URL:

```
/scout-research https://careers.stripe.com/listing/senior-engineer
```

### 3. Analyze a job

Get match scores, gap analysis, and resume strategy:

```
/scout-analyze JOB-STRIPE-a1b2c3
```

### 4. Generate a resume

Create a tailored resume for the job:

```
/scout-resume JOB-STRIPE-a1b2c3
```

To improve an existing resume with surgical edits:

```
/scout-resume JOB-STRIPE-a1b2c3 --improve
```

### 5. Generate a cover letter

```
/scout-cover-letter JOB-STRIPE-a1b2c3
```

### 6. Prepare for interviews

```
/scout-interview-prep JOB-STRIPE-a1b2c3
```

### 7. Track your pipeline

See what needs attention next:

```
/scout-pipeline next
```

Record an application:

```
/scout-pipeline apply JOB-STRIPE-a1b2c3
```

View pipeline overview:

```
/scout-pipeline pipeline
```

## Skills Reference

| Skill | Description | Key Features |
|-------|-------------|-------------|
| `scout-setup` | Initialize workspace | Config creation, resume parsing, profile management |
| `scout-companies` | Find target companies | Location-aware, scoring, seed/exclusion lists |
| `scout-research` | Research companies + import jobs | Company name, URL, or pasted text input |
| `scout-analyze` | Analyze job fit | Match scoring, gap analysis, role archetypes |
| `scout-resume` | Generate/improve resumes | Two-pass generation, three-phase improvement |
| `scout-cover-letter` | Generate cover letters | Two-pass with anti-pattern enforcement |
| `scout-interview-prep` | Interview preparation | Talking points, STAR stories, questions to ask |
| `scout-pipeline` | Pipeline management | Action dashboard, status tracking, learning |

## Data Files

All data is stored locally in your project directory:

```
config.json                     # Search preferences and configuration
data/
  candidate-profile.json        # Parsed resume profile
  pipeline.json                 # Application pipeline state
  jobs-<location-slug>.json     # Jobs by location
  companies-<location-slug>.json # Scouted companies by location
  research/<company-slug>.json  # Company research
  learned-preferences.json      # Patterns learned from your feedback
input/
  base-resume.md                # Your source resume
output/
  resumes/                      # Generated resumes
  cover-letters/                # Generated cover letters
  analysis/                     # Job analyses
  interview-prep/               # Interview prep docs
```

## Troubleshooting

**`scout-tools` not found:**
```bash
uv pip install talent-scout-scripts
```

**PDF generation fails:**
WeasyPrint is optional. Skills default to Markdown output. To enable PDF:
```bash
brew install weasyprint
export DYLD_LIBRARY_PATH=/opt/homebrew/lib  # macOS
```

**"No profile found" errors:**
Run `/scout-setup` first — or `/scout-setup refresh-profile` if your base resume changed.

**Location classification questions:**
```bash
scout-tools data classify-location "San Francisco, CA"
```
