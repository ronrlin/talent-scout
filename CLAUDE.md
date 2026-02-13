# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Talent Scout is a Python CLI + API tool for job search automation. It uses Claude API to power services that scout companies, research jobs, find connections, and generate customized resumes. The architecture follows a service layer pattern: CLI and API share the same framework-agnostic services.

## Architecture

```
┌─────────┐     ┌──────────┐
│  CLI    │     │ REST API │
│(scout.py│     │(FastAPI) │
└────┬────┘     └────┬─────┘
     └───────┬───────┘
             │
    ┌────────▼─────────┐
    │  Service Layer   │  ← Framework-agnostic, no console output
    │  (services/)     │     Returns Pydantic models, raises typed exceptions
    └────────┬─────────┘
             │
       ┌─────┼──────┐
       │     │      │
  ┌────▼┐ ┌──▼──┐ ┌─▼───┐
  │Skills│ │Data │ │Pipe │
  │     │ │Store│ │line │
  └──┬──┘ └─────┘ └─────┘
     │
  ┌──▼──┐
  │Claude│
  │Client│
  └─────┘
```

**5 Services:** JobService, ProfileService, DiscoveryService, ComposerService, CorpusService
**7 Skills:** Stateless, reused by services (SkillContext in → SkillResult out)

## Tech Stack

- Python 3.11+ with CLI subcommands (`scout <command>`)
- FastAPI REST API (`scout serve` or `uvicorn api.app:create_app --factory`)
- Claude API (Anthropic) for AI capabilities
- Pydantic v2 for request/response models
- JSON files for data storage
- Markdown for base resume and generated documents; WeasyPrint for PDF, python-docx for DOCX generation

## Development Setup

```bash
# Install in development mode
pip install -e ".[test]"

# Set API key
export ANTHROPIC_API_KEY=YOUR_API_KEY_HERE

# For PDF generation (macOS), set library path
export DYLD_LIBRARY_PATH=/opt/homebrew/lib

# Run CLI
python scout.py --help
python scout.py companies --location "Palo Alto, CA"

# Run API server
python scout.py serve --port 8000
# Or: uvicorn api.app:create_app --factory --reload

# Run tests
pytest tests/ -v
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
scout apply <job_id> [--via "method"] [--notes "text"] [--date "ISO"]
scout status <job_id> [stage] [--outcome accepted|rejected|declined|ghosted|withdrawn]
scout pipeline [--stage <stage>]
scout next
scout jobs [--stage <stage>]
scout serve [--host 0.0.0.0] [--port 8000] [--reload]
```

## API Endpoints

All under `/api/v1/`, require `X-API-Key` header. Key auto-generated in `data/.api-key` on first `scout serve`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile` | Get candidate profile |
| POST | `/profile/refresh` | Re-parse profile (async) |
| POST | `/companies/scout` | Scout companies (async) |
| GET | `/companies` | List scouted companies |
| POST | `/research` | Research company (async) |
| POST | `/jobs/import/url` | Import job from URL (async) |
| POST | `/jobs/import/markdown` | Import job from markdown (async) |
| POST | `/learn` | Learn from feedback (async) |
| GET | `/jobs` | List jobs (filters: company, stage, location) |
| GET | `/jobs/{id}` | Get job detail |
| DELETE | `/jobs/{id}` | Delete job |
| POST | `/jobs/{id}/apply` | Record application |
| PUT | `/jobs/{id}/status` | Set pipeline stage |
| POST | `/jobs/{id}/close` | Close with outcome |
| GET | `/jobs/{id}/history` | Pipeline history |
| POST | `/jobs/{id}/notes` | Add note |
| POST | `/jobs/{id}/analyze` | Analyze job (async) |
| POST | `/jobs/{id}/resume` | Generate resume (async) |
| POST | `/jobs/{id}/resume/improve` | Improve resume (async) |
| POST | `/jobs/{id}/cover-letter` | Generate cover letter (async) |
| POST | `/jobs/{id}/interview-prep` | Interview prep (async) |
| GET | `/jobs/{id}/artifacts/{type}` | Download artifact (pdf/docx/md) |
| GET | `/pipeline` | Pipeline overview |
| GET | `/pipeline/next` | Action dashboard |
| GET | `/pipeline/stats` | Pipeline stats |
| POST | `/corpus/build` | Build corpus (async) |
| POST | `/corpus/update` | Update corpus (async) |
| GET | `/corpus/stats` | Corpus stats |
| GET | `/tasks/{id}` | Poll async task status |
| GET | `/tasks` | List recent tasks |

Async endpoints return `202 { "task_id": "..." }` — poll via `GET /tasks/{id}`.

## Pipeline Stages

```
discovered → researched → resume_ready → applied → screening → interviewing → offer → closed
```

- Commands auto-advance state on success (e.g., `scout analyze` → `researched`)
- `scout status` can manually set any stage (forward or backward)
- Pipeline state stored in `data/pipeline.json`
- Closed outcomes: `accepted`, `rejected`, `declined`, `ghosted`, `withdrawn`

## Directory Structure

```
scout.py                    # CLI (uses services, Rich output)
config.json                 # User configuration
config_loader.py            # Config and location utilities
data_store.py               # Centralized JSON file data access
pipeline_store.py           # Pipeline state machine
claude_client.py            # Anthropic API wrapper

services/                   # Framework-agnostic business logic
  base_service.py           # Shared: config, client, learned prefs
  exceptions.py             # Typed exception hierarchy
  models.py                 # Pydantic request/response schemas
  job_service.py            # CRUD for jobs + pipeline
  profile_service.py        # Candidate profile management
  discovery_service.py      # Company scouting, research, import
  composer_service.py       # Analysis, resume, cover letter, interview prep
  corpus_service.py         # Experience bullet corpus
  document_converter.py     # PDF/DOCX conversion
  task_manager.py           # In-process async task runner

api/                        # FastAPI HTTP layer
  app.py                    # App factory, CORS, error handlers
  auth.py                   # API key auth
  dependencies.py           # FastAPI Depends() providers
  routers/                  # One router per domain

agents/                     # Legacy agent layer (deprecated)
skills/                     # Stateless skills (reused by services)
templates/                  # CSS templates for PDF generation
input/                      # User inputs (base-resume.md, etc.)
data/                       # JSON data files
output/                     # Generated outputs

tests/
  conftest.py               # Shared fixtures
  services/                 # Service unit tests
  api/                      # API integration tests
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

## Docker

```bash
# Run API via Docker
docker-compose up --build

# CLI via Docker
docker exec talent-scout python scout.py jobs
```

## Testing

```bash
pytest tests/ -v                        # All tests
pytest tests/services/ -v               # Service unit tests
pytest tests/api/ -v                    # API integration tests
pytest tests/ --cov=services --cov=api  # With coverage
```
