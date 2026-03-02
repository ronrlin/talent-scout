# Analysis Output Schema

JSON schema for the job analysis output saved to `output/analysis/<job-id>-analysis.json`.

## File Envelope

```json
{
  "job_id": "JOB-COMPANY-HASH",
  "job": { /* original job record */ },
  "analysis": { /* analysis result — schema below */ },
  "analyzed_at": "2026-01-15T12:00:00+00:00"
}
```

## Analysis Result Schema

```json
{
  "job_summary": {
    "title": "Job title",
    "company": "Company name",
    "role_archetype": "org_leadership | team_leadership | tech_lead | product | data | ml | infra | ic",
    "business_mission": "What this role ultimately exists to achieve",
    "key_responsibilities": ["Top 5 responsibilities"],
    "required_skills": ["Must-have skills"],
    "preferred_skills": ["Nice-to-have skills"],
    "experience_required": "Years and type of experience",
    "education_required": "Education requirements"
  },
  "match_assessment": {
    "overall_score": 0,
    "strengths": ["Concrete reasons this candidate is a strong fit"],
    "gaps": ["Real gaps or weaker areas relative to the role"],
    "transferable_skills": ["Skills that clearly translate into this role"],
    "domain_connections": [
      {
        "candidate_experience": "Specific role or project",
        "target_domain": "Aspect of the target role",
        "connection_type": "analogous_problem | shared_algorithm | industry_parallel | operational_overlap",
        "underlying_problem_type": "e.g., optimization, classification, forecasting",
        "reasoning": "Why these are structurally the same problem"
      }
    ]
  },
  "resume_recommendations": {
    "positioning_strategy": "How the resume should be framed overall for this role",
    "skills_to_emphasize": ["Existing skills to foreground"],
    "experience_to_highlight": ["Specific bullets or roles to feature"],
    "keywords_to_include": ["ATS-relevant keywords from the job description"],
    "sections_to_adjust": ["Summary, Experience bullets, Skills section"],
    "language_shifts": ["Specific wording changes to improve alignment"]
  },
  "cover_letter_points": ["Key narrative points tailored to this role"],
  "interview_prep": ["Topics, tradeoffs, or examples to prepare"],
  "confidence_flags": ["Areas where the candidate should proactively control the narrative"]
}
```

## Field Notes

- **overall_score**: 0-100 integer. Higher means stronger match.
- **role_archetype**: Must be one of the 8 constrained values listed above. See `role-archetypes.md` for definitions.
- **domain_connections**: The most valuable part of the analysis. Captures structural parallels between the candidate's experience and the target role's problem domain.
- **confidence_flags**: Areas where the candidate's narrative may be questioned. Helps interview prep focus on controlling these narratives proactively.
