# Research Output Schema

JSON schema for company research saved to `data/research/<company-slug>.json`.

```json
{
  "company": {
    "company_name": "Official Company Name",
    "website": "https://...",
    "description": "What the company does in 2-3 sentences",
    "mission": "Company mission statement or values",
    "industry": "Industry/sector",
    "founded": "Year founded",
    "headquarters": "City, State",
    "employee_count": "Approximate employee count",
    "public": true,
    "stock_ticker": "TICK or null",
    "recent_news": [
      {"headline": "...", "summary": "...", "date": "approximate date"}
    ],
    "financial_summary": "Brief financial health summary",
    "engineering_culture": "What's known about eng culture, tech stack",
    "leadership": [
      {"name": "...", "title": "...", "linkedin": "url or null"}
    ],
    "office_locations": ["City, State"],
    "relevance_notes": "Why this company might be good for the target role"
  },
  "jobs": [
    {
      "id": "JOB-COMPANY-HASH",
      "company": "Company Name",
      "title": "Job Title",
      "department": "Engineering/Product/etc",
      "location": "City, State or Remote",
      "location_type": "<location_slug>",
      "url": "careers page URL or null",
      "posted_date": "approximate date or null",
      "requirements_summary": "Key requirements",
      "match_score": 85,
      "match_notes": "Why this role matches",
      "source": "discovered"
    }
  ],
  "careers_page": "URL to company careers page",
  "search_notes": "Notes about the job search",
  "researched_at": "2026-01-15T12:00:00+00:00"
}
```
