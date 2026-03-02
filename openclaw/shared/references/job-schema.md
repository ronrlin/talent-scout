# Job Schema

Structure of job dictionaries stored in `data/jobs-{location_slug}.json`.

## Job Fields

```json
{
  "id": "JOB-COMPANY-HEXID — unique identifier",
  "company": "Company Name",
  "title": "Job Title",
  "department": "Engineering/Product/etc",
  "location": "City, State or Remote",
  "location_type": "location_slug (e.g., palo-alto-ca, remote)",
  "url": "Job posting URL or null",
  "posted_date": "Date string or null",
  "requirements_summary": "Key requirements text",
  "responsibilities_summary": "Key responsibilities text",
  "compensation": "Salary info or null",
  "match_score": 0-100,
  "match_notes": "Why this role matches the candidate profile",
  "source": "discovered | imported",
  "imported_at": "ISO timestamp (imported jobs only)",
  "source_file": "filename (markdown imports only)"
}
```

## Job ID Format

- Discovered jobs: `JOB-{COMPANY_SLUG[:8]}-{UUID_HEX[:6]}`
- Example: `JOB-GOOGLE-A1B2C3`

## Data File Structure

Jobs are stored by location slug in `data/jobs-{slug}.json`:

```json
{
  "jobs": [ ... ],
  "updated_at": "ISO timestamp"
}
```

## Internal Fields

- `_location_slug` — added at read time by `get_job()` and `get_jobs()`, not persisted
