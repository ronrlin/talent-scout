You are analyzing resume bullets to build a skills corpus.

For each bullet, extract:
1. skills_demonstrated: List of specific skills this bullet proves (e.g., "Python", "team leadership", "ML systems", "data engineering")
2. themes: Categories like "customer-facing", "data engineering", "team management", "analytics", "production systems", "autonomous systems"
3. role_lens: Best fit - "engineering", "product", "program", or "solutions"

Return a JSON array where each element has:
{
  "bullet_index": <index from input>,
  "skills_demonstrated": ["skill1", "skill2", ...],
  "themes": ["theme1", "theme2", ...],
  "role_lens": "engineering|product|program|solutions"
}

Be specific with skills - extract actual technologies, methodologies, and competencies mentioned or implied.
For themes, use broad categories that help match bullets to job types.
