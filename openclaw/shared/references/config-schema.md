# Config Schema

Structure of `config.json` at project root.

```json
{
  "user": {
    "name": "string — candidate full name",
    "linkedin_url": "string — LinkedIn profile URL",
    "base_resume_path": "string — path to base resume markdown (e.g., ./input/base-resume.md)",
    "email": "string — candidate email"
  },
  "preferences": {
    "locations": ["City, State", "..."],
    "include_remote": true,
    "roles": ["target role titles..."],
    "min_company_size": 100,
    "prefer_public_companies": true,
    "companies_per_location": 30,
    "output_format": "pdf | docx | both",
    "pipeline": {
      "follow_up_days": 7,
      "follow_up_reminder_days": [7, 14],
      "auto_ghost_days": 30
    }
  },
  "seeds": {
    "include": "./input/target-companies.json",
    "exclude": "./input/excluded-companies.json"
  }
}
```

## Location Format

Locations use `"City, State"` format. The system automatically expands to metro areas. Examples:
- `"Palo Alto, CA"` — covers Silicon Valley / SF Bay Area
- `"Boca Raton, FL"` — covers South Florida

## Location Slugs

Location strings are converted to slugs for file naming:
- `"Palo Alto, CA"` → `"palo-alto-ca"`
- `"remote"` → `"remote"`

Used in data filenames: `data/jobs-palo-alto-ca.json`, `data/companies-remote.json`
