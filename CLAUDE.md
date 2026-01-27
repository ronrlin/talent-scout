# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Talent Scout is a Python CLI tool for job search automation. It uses Claude API to power agents that scout companies, research jobs, find connections, and generate customized resumes.

## Tech Stack

- Python 3.11+ with CLI subcommands (`scout <command>`)
- Claude API (Anthropic) for AI capabilities
- JSON files for data storage
- Markdown to PDF for resume/cover letter generation

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
python scout.py companies --location boca
```

## CLI Commands

```bash
scout companies [--location boca|palo|remote] [--count 15]
scout research <company_name>
scout analyze <job_id>
scout resume <job_id>
scout resume-improve <job_id>
scout resume-gen <job_id>
scout cover-letter <job_id>
scout cover-letter-gen <job_id>
```

## Directory Structure

- `agents/` - Agent implementations (company_scout, company_researcher, etc.)
- `input/` - User inputs (base resume, target/excluded company lists)
- `data/` - Generated data (companies, jobs, research, connections)
- `output/` - Final outputs (resumes, cover letters, outreach emails)

## Key Files

- `config.json` - User configuration (API keys, preferences, paths)
- `data/companies-{boca|palo|remote}.json` - Target company lists
- `data/jobs-{boca|palo|remote}.json` - Discovered job openings
- `PRD.md` - Full product requirements document
