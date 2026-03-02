# Location Classification Rules

How job locations are classified into location slugs for data sharding.

## Slug Format

Location strings are converted to slugs: `"City, State"` → `"city-state"` (lowercase, non-alphanumeric replaced with hyphens).

Examples:
- `"Palo Alto, CA"` → `"palo-alto-ca"`
- `"Boca Raton, FL"` → `"boca-raton-fl"`
- `"Remote"` → `"remote"`

## Metro Area Expansion

Each configured location automatically expands to cover the surrounding metro area. The classifier checks whether a job's location falls within any configured metro area.

Example expansions:
- `"Palo Alto, CA"` covers: San Francisco, San Jose, Mountain View, Sunnyvale, Cupertino, Menlo Park, Redwood City, Santa Clara, and the broader SF Bay Area / Silicon Valley
- `"Boca Raton, FL"` covers: Fort Lauderdale, Miami, West Palm Beach, Delray Beach, and the broader South Florida area

## Classification Logic

For each job location:
1. Check if it matches any configured metro area → use that location's slug
2. Check if it indicates remote/distributed/work-from-anywhere → use `"remote"` slug (if remote enabled)
3. Check for hybrid with remote option → use `"remote"` slug
4. If no match and remote is enabled → default to `"remote"`
5. If no match and remote is NOT enabled → default to the first configured location's slug

## Using the Classifier

Run:
```bash
scout-tools data classify-location "<location string>"
```

Returns the appropriate location slug. Always use this rather than guessing — the metro area expansion logic is non-trivial.

## Data Files

Jobs are sharded by location slug:
- `data/jobs-palo-alto-ca.json`
- `data/jobs-remote.json`
- `data/companies-palo-alto-ca.json`
