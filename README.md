# Talent Scout

AI-powered job search automation tool that helps you scout companies, research job openings, and generate customized resumes and cover letters using Claude API.

## Prerequisites

- **Python 3.11+** - Required for running the CLI
- **Anthropic API Key** - Get one at [console.anthropic.com](https://console.anthropic.com)
- **WeasyPrint dependencies** (for PDF generation):
  - macOS: `brew install pango`
  - Ubuntu/Debian: `apt-get install libpango-1.0-0 libpangocairo-1.0-0`

## Installation

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd talent-scout

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

### 2. Set Up Your API Key

Create a `.env` file in the project root:

```bash
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

Before running commands, load the environment:

```bash
export $(cat .env | xargs)
```

Or on macOS/Linux, add to your shell profile for persistence:

```bash
echo 'export ANTHROPIC_API_KEY=your-api-key-here' >> ~/.zshrc  # or ~/.bashrc
source ~/.zshrc
```

### 3. Configure PDF Generation (macOS only)

If using WeasyPrint for PDF generation:

```bash
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

## Configuration

### config.json

Edit `config.json` to customize your profile:

```json
{
  "user": {
    "name": "Your Name",
    "linkedin_url": "www.linkedin.com/in/yourprofile",
    "base_resume_path": "./input/base-resume.docx",
    "email": "your.email@example.com"
  },
  "preferences": {
    "locations": [
      "Palo Alto, CA",
      "Boca Raton, FL"
    ],
    "include_remote": true,
    "target_roles": [
      "Engineering Manager",
      "Software Manager",
      "Technical Product Manager"
    ],
    "min_company_size": 100,
    "prefer_public_companies": true,
    "companies_per_location": 15
  },
  "seeds": {
    "include": "./input/target-companies.json",
    "exclude": "./input/excluded-companies.json"
  }
}
```

**Configuration fields:**

| Field | Description |
|-------|-------------|
| `user.name` | Your full name (used in resumes/cover letters) |
| `user.linkedin_url` | Your LinkedIn profile URL |
| `user.base_resume_path` | Path to your base resume (Word .docx format) |
| `user.email` | Your email address |
| `preferences.locations` | List of locations in "City, State" format (e.g., `"Palo Alto, CA"`) |
| `preferences.include_remote` | Set to `true` to include remote/distributed job opportunities |
| `preferences.target_roles` | Job titles you're targeting |
| `preferences.min_company_size` | Minimum employee count |
| `preferences.prefer_public_companies` | Prioritize public companies |
| `preferences.companies_per_location` | Number of companies to scout per location |

### Location Configuration

Locations are specified in "City, State" format (e.g., `"Palo Alto, CA"`, `"Austin, TX"`). The system automatically expands each location to include the surrounding metropolitan area:

- `"Palo Alto, CA"` → San Francisco Bay Area / Silicon Valley (San Jose, Mountain View, Sunnyvale, etc.)
- `"Boca Raton, FL"` → South Florida (Miami, Fort Lauderdale, Palm Beach, etc.)
- `"Seattle, WA"` → Seattle metropolitan area (Bellevue, Redmond, Kirkland, etc.)
- `"Austin, TX"` → Austin metropolitan area (Round Rock, Cedar Park, etc.)

Jobs found in any city within the metropolitan area are automatically grouped under the configured location.

**Remote Jobs:** Set `include_remote: true` to also search for remote/distributed positions. Remote jobs are stored separately from location-specific jobs.

## Input Files Setup

### 1. Base Resume

Place your resume in Word format at `input/base-resume.docx`. This is used as the foundation for generating customized resumes.

### 2. Target Companies

Edit `input/target-companies.json` to add companies you want to prioritize:

```json
{
  "description": "Companies to prioritize in the search.",
  "companies": [
    {
      "name": "Google",
      "notes": "Strong engineering culture"
    },
    {
      "name": "Stripe",
      "notes": "Fintech leader, remote-friendly"
    }
  ]
}
```

### 3. Excluded Companies

Edit `input/excluded-companies.json` to list companies to skip:

```json
{
  "description": "Companies to exclude from search results.",
  "companies": [
    {
      "name": "Previous Employer Inc",
      "reason": "previous employer"
    },
    {
      "name": "Not Interested Corp",
      "reason": "not interested"
    }
  ]
}
```

## Directory Structure

```
talent-scout/
├── scout.py              # Main CLI entry point
├── config.json           # Your configuration
├── .env                  # API key (create this)
├── agents/               # AI agent implementations
├── input/
│   ├── base-resume.docx        # Your base resume
│   ├── target-companies.json   # Companies to prioritize
│   └── excluded-companies.json # Companies to skip
├── data/
│   ├── companies-{location-slug}.json  # Scouted company lists (e.g., companies-palo-alto-ca.json)
│   ├── jobs-{location-slug}.json       # Discovered job openings (e.g., jobs-boca-raton-fl.json)
│   ├── jobs-remote.json                # Remote job openings (if include_remote: true)
│   ├── research/                       # Company research dossiers
│   └── connections/                    # Connection data
└── output/
    ├── resumes/          # Generated resumes (PDF + Markdown)
    ├── cover-letters/    # Generated cover letters
    ├── analysis/         # Job analysis results
    └── outreach/         # Cold outreach emails
```

## Quick Start Workflow

### 1. Scout Companies

Find target companies in a specific location:

```bash
scout companies --location "Palo Alto, CA" --count 10
scout companies --location "Boca Raton, FL" --count 15
scout companies --location remote
scout companies --location all  # Scout all configured locations
```

### 2. Research a Company

Deep-dive into a company and discover job openings:

```bash
scout research "Google"
scout research "Stripe"
```

Or import a job directly from a URL:

```bash
scout research https://jobs.lever.co/company/job-id
```

### 3. Review Jobs

List all discovered jobs:

```bash
scout jobs                      # All jobs
scout jobs --location palo      # Jobs in Palo Alto
scout jobs --company Google     # Jobs at Google
```

### 4. Remove Unwanted Jobs

Delete jobs that don't fit (teaches the system your preferences):

```bash
scout delete JOB-GOOGLE-ABC123 --reason "Too senior"
```

### 5. Learn Your Preferences

After importing/deleting jobs, train the system:

```bash
scout learn
```

### 6. Analyze a Job

Get a detailed match analysis:

```bash
scout analyze JOB-GOOGLE-ABC123
```

### 7. Generate Resume

Create a customized resume for a specific job:

```bash
scout resume JOB-GOOGLE-ABC123
```

Output: `output/resumes/Your Name Resume - Google.pdf`

### 8. Generate Cover Letter

Create a tailored cover letter:

```bash
scout cover-letter JOB-GOOGLE-ABC123
```

Output: `output/cover-letters/Cover Letter Google.pdf`

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `scout companies` | Scout target companies by location |
| `scout research <company>` | Research a company or import job from URL |
| `scout jobs` | List all discovered job opportunities |
| `scout delete <job_id>` | Remove a job and provide feedback |
| `scout learn` | Analyze feedback to improve targeting |
| `scout analyze <job_id>` | Analyze job requirements vs your profile |
| `scout resume <job_id>` | Generate customized resume |
| `scout resume-improve <job_id>` | Iteratively improve resume |
| `scout resume-gen <job_id>` | Regenerate PDF from edited markdown |
| `scout cover-letter <job_id>` | Generate tailored cover letter |
| `scout cover-letter-gen <job_id>` | Regenerate PDF from edited markdown |
| `scout connections <company>` | Find connections at a company |
| `scout outreach <company>` | Generate cold outreach email |
| `scout import-jobs` | Import jobs from markdown files |

## Typical Session Example

```bash
# Load environment
export $(cat .env | xargs)

# Scout companies in Boca Raton
scout companies --location "Boca Raton, FL" --count 10

# Research a specific company
scout research "ModMed"

# List discovered jobs
scout jobs --company ModMed

# Analyze a promising job
scout analyze JOB-MODMED-ABC123

# Generate application materials
scout resume JOB-MODMED-ABC123
scout cover-letter JOB-MODMED-ABC123

# Files are saved to output/resumes/ and output/cover-letters/
```

## Troubleshooting

### "ANTHROPIC_API_KEY environment variable not set"

Make sure to load your `.env` file:

```bash
export $(cat .env | xargs)
```

### PDF generation fails on macOS

Install required libraries and set the library path:

```bash
brew install pango
export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

### "No module named 'anthropic'"

Install dependencies:

```bash
pip install -e .
```

## License

MIT
