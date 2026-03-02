# talent-scout-scripts

CLI tools for [Talent Scout](https://github.com/ronlin/talent-scout) OpenClaw skills.

## Install

```bash
uv pip install talent-scout-scripts
```

## Usage

```bash
scout-tools --help
scout-tools data --help
scout-tools pipeline --help
scout-tools convert --help
scout-tools edit --help
```

## Subcommand Groups

### `data` — Job and profile data operations

```
get-job, save-job, update-job, list-jobs, delete-job, save-jobs,
job-exists, record-deleted-job, get-deleted-jobs,
get-research, save-research, get-companies, save-companies,
get-profile, save-profile, get-learned-prefs, save-learned-prefs,
get-corpus, save-corpus, classify-location, check-profile-hash,
invalidate-index
```

### `pipeline` — Application tracking

```
create, advance, set-status, close, remove,
get, get-all, get-by-status, get-history, get-stats,
record-artifact, add-note, actionable, overview
```

### `convert` — Document format conversion

```
resume <input.md> <format>       # Convert resume to pdf/docx/both
cover-letter <input.md> <format> # Convert cover letter to pdf/docx/both
```

### `edit` — Resume editing

```
apply <resume.md> <edits.json>   # Apply edit plan to resume
```

## Output

All commands output JSON to stdout. Errors go to stderr with non-zero exit codes.

## Requirements

- Python 3.11+
- Talent Scout project directory (data files, config.json)
- WeasyPrint (optional, for PDF conversion)
