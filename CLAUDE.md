# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Talent Scout is a Python CLI tool for job search automation. It uses Claude API to power agents that scout companies, research jobs, find connections, and generate customized resumes.

## Tech Stack

- Python 3.11+ with CLI subcommands (`scout <command>`)
- Claude API (Anthropic) for AI capabilities
- JSON files for data storage
- Markdown for base resume and generated documents; WeasyPrint for PDF, python-docx for DOCX generation

## Development Setup

```bash
# Install in development mode
pip install -e .

# Set API key
export ANTHROPIC_API_KEY=YOUR_API_KEY_HERE

# For PDF generation (macOS), set library path
export DYLD_LIBRARY_PATH=/opt/homebrew/lib

# Run CLI
python scout.py --help
python scout.py companies --location "Palo Alto, CA"
```

## CLI Commands

```bash
scout companies [--location "City, State"|remote|all] [--count 15]
scout research <company_name>
scout analyze <job_id>
scout resume <job_id> [--format pdf|docx|both]
scout resume-improve <job_id> [--format pdf|docx|both]
scout resume-gen <job_id> [--format pdf|docx|both]
scout cover-letter <job_id> [--format pdf|docx|both]
scout cover-letter-gen <job_id> [--format pdf|docx|both]
scout interview-prep <job_id>
```

## Location Configuration

Locations are configured in `config.json` using "City, State" format. The system automatically expands to metro areas. Set `include_remote: true` for remote jobs.

```json
"preferences": {
  "locations": ["Palo Alto, CA", "Boca Raton, FL"],
  "include_remote": true
}
```

## Output Format Configuration

Output format for resumes and cover letters defaults to `preferences.output_format` in `config.json`. Override per-command with `--format`.

```json
"preferences": {
  "output_format": "both"
}
```

Options: `"pdf"` (default), `"docx"`, `"both"` (generates PDF + DOCX).

## Directory Structure

- `agents/` - Agent implementations (company_scout, company_researcher, etc.)
- `input/` - User inputs (base resume, target/excluded company lists)
- `data/` - Generated data (companies, jobs, research, connections)
- `output/` - Final outputs (resumes, cover letters, interview prep, outreach emails)

## Key Files

- `config.json` - User configuration (preferences, paths, locations)
- `config_loader.py` - Configuration and location utilities
- `data/companies-{location-slug}.json` - Target company lists (e.g., companies-palo-alto-ca.json)
- `data/jobs-{location-slug}.json` - Discovered job openings (e.g., jobs-boca-raton-fl.json)
- `PRD.md` - Full product requirements document
