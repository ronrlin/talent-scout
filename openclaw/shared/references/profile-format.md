# Profile Format

## Candidate Profile (`data/candidate-profile.json`)

Parsed representation of the candidate's base resume, stored as JSON.

```json
{
  "name": "Candidate Name",
  "email": "email@example.com",
  "linkedin": "linkedin URL",
  "summary": "Professional summary text",
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "dates": "Start - End",
      "bullets": ["achievement 1", "achievement 2"]
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "Degree Type",
      "field": "Field of Study",
      "year": "Graduation Year"
    }
  ],
  "skills": ["skill1", "skill2"],
  "source_hash": "SHA-256 hash of input/base-resume.md at parse time"
}
```

## Base Resume (`input/base-resume.md`)

The source-of-truth resume in Markdown format. All generated resumes must trace claims back to this file (or to additional context provided at generation time).

Structure:
- `# Name` heading
- Contact info line
- `## Professional Summary`
- `## Professional Experience` with `### Company — Title` subsections
- `## Education`
- Optional additional sections
