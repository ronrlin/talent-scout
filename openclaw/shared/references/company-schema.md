# Company Schema

JSON schema for scouted companies saved to `data/companies-<location-slug>.json`.

Each file contains an array of company objects:

```json
[
  {
    "name": "Company Name",
    "website": "https://example.com",
    "hq_location": "City, State",
    "industry": "Industry description",
    "employee_count": "1000-5000",
    "public": true,
    "priority_score": 85,
    "notes": "Why this company is a good fit"
  }
]
```

## Field Notes

- **priority_score**: 0-100 integer. Higher means better fit for the job search criteria.
- **employee_count**: String range (e.g., "100-500", "1000-5000", "10000+").
- **public**: Boolean indicating whether the company is publicly traded.
- **notes**: Brief explanation of why this company matches the user's target roles and preferences.
