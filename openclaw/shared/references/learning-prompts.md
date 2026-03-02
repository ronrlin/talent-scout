# Learning Prompts

Prompts for analyzing job search feedback to improve targeting. Used by `scout-pipeline learn`.

## Combined Learning (both imported and deleted jobs)

When BOTH positive (imported) and negative (deleted) feedback exists, analyze them together:

**Positive signals** — jobs the user manually imported represent REAL interest. Analyze:
1. Title patterns, key skills, experience level
2. Industry patterns and company characteristics
3. What makes these roles attractive

**Negative signals** — jobs the user deleted represent roles to AVOID. Analyze:
1. Title patterns to deprioritize
2. Skills/requirements indicating poor fit
3. Company characteristics to avoid
4. Role aspects that are unappealing

**Combined output schema:**
```json
{
  "positive_analysis": {
    "title_patterns": ["job title patterns from imported jobs"],
    "key_skills": ["skills that appear in desired roles"],
    "experience_level": "target seniority level",
    "industry_patterns": ["appealing industries"],
    "company_characteristics": ["desirable company traits"],
    "compelling_factors": ["what makes these roles attractive"]
  },
  "negative_analysis": {
    "title_patterns_to_avoid": ["job title patterns to deprioritize"],
    "skills_mismatch": ["skills/requirements that indicate poor fit"],
    "company_red_flags": ["company characteristics to avoid"],
    "role_red_flags": ["role aspects that are unappealing"]
  },
  "improved_targeting": {
    "primary_titles": ["exact job titles to prioritize"],
    "secondary_titles": ["related titles worth considering"],
    "titles_to_avoid": ["job titles to deprioritize or exclude"],
    "must_have_keywords": ["keywords that should appear in ideal postings"],
    "nice_to_have_keywords": ["positive signal keywords"],
    "red_flag_keywords": ["keywords that indicate poor fit"],
    "ideal_company_profile": "description of ideal company",
    "companies_to_avoid": "types of companies to deprioritize"
  },
  "scoring_adjustments": {
    "boost_factors": ["factors that should increase match score"],
    "penalty_factors": ["factors that should decrease match score"]
  },
  "prompt_improvements": {
    "job_search_additions": "text to add to job search prompts",
    "job_search_exclusions": "text about what to exclude",
    "company_scout_additions": "text to add to company scouting prompts",
    "match_scoring_criteria": "comprehensive scoring criteria including penalties"
  },
  "insights": "2-3 sentence summary combining positive preferences and things to avoid"
}
```

## Positive-Only Learning (imported jobs only)

When only imported jobs exist (no deletions), focus on understanding what the user wants:
1. Identify patterns in job titles, responsibilities, requirements
2. Understand appealing industries and company types
3. Extract repeated skills and qualifications
4. Identify what makes roles attractive (seniority, scope, team size)
5. Note company characteristic patterns (size, stage, culture)

## Negative-Only Learning (deleted jobs only)

When only deleted jobs exist (no imports), focus on what to avoid:
1. Why these jobs might have been rejected
2. Title patterns to deprioritize
3. Unappealing company characteristics
4. Keywords or requirements signaling poor fit
5. Seniority or scope mismatches
