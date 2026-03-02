---
name: scout-setup
description: "Set up Talent Scout job search. Use when user wants to configure job search, parse resume into profile, or initialize workspace."
argument-hint: "[refresh-profile]"
allowed-tools: Read, Write, Bash, Glob, Grep
metadata: {"openclaw": {"requires": {"bins": ["scout-tools"]}, "install": [{"id": "scripts", "kind": "uv", "package": "talent-scout-scripts", "bins": ["scout-tools"], "label": "Install Talent Scout tools"}]}}
---

# scout-setup

Set up or reconfigure the Talent Scout workspace. Handles config creation, profile parsing, and workspace verification.

**NEVER edit data files directly. Always use `scout-tools` for all data operations.**

## Arguments

- No argument — full setup check (config + resume + profile + directories)
- `refresh-profile` — re-parse the base resume into a fresh profile

---

## Full Setup

### 1. Check for config.json

If `config.json` does NOT exist, guide the user through creating one.

Ask the user for:
- **Name** — full name for resumes and cover letters
- **Email** — contact email
- **LinkedIn URL** — LinkedIn profile URL
- **Locations** — target job locations (e.g., "Palo Alto, CA", "Boca Raton, FL")
- **Include remote?** — whether to include remote jobs (yes/no)
- **Target roles** — roles to search for (e.g., "Engineering Manager", "Director of Engineering")

Create `config.json` following the schema in `references/config-schema.md`:

```json
{
  "user": {
    "name": "<name>",
    "linkedin_url": "<linkedin>",
    "base_resume_path": "./input/base-resume.md",
    "email": "<email>"
  },
  "preferences": {
    "locations": ["<location1>", "<location2>"],
    "include_remote": true,
    "roles": ["<role1>", "<role2>"],
    "min_company_size": 100,
    "prefer_public_companies": true,
    "companies_per_location": 30,
    "output_format": "pdf",
    "pipeline": {
      "follow_up_days": 7,
      "follow_up_reminder_days": [7, 14],
      "auto_ghost_days": 30
    }
  }
}
```

If `config.json` already exists, read and display the current configuration.

### 2. Check for Base Resume

Verify `input/base-resume.md` exists.

If it does NOT exist:
- Check if `input/` directory exists; create if missing
- Tell the user: "Place your base resume as `input/base-resume.md` in Markdown format. This is the ground truth for all generated resumes and cover letters."
- Stop setup until the resume is in place

If it exists, confirm it's present and show a brief summary (word count, section headers).

### 3. Parse Resume into Profile

Check if `data/candidate-profile.json` exists.

If it does NOT exist, or if the user requested `refresh-profile`:

1. Read `input/base-resume.md`
2. Parse the resume into a structured profile following the schema in `references/profile-format.md`:

   Extract:
   - **identity** — name, email, phone, linkedin, location
   - **summary** — professional summary (2-3 sentences)
   - **experience** — company, title, dates, highlights, skills_used for each role
   - **skills** — technical, leadership, domains
   - **education** — institution, degree, field, year

3. Read config preferences and include in profile:
   - target_roles, locations, include_remote

4. Compute a SHA-256 hash of `input/base-resume.md` and store as `source_resume_hash`

5. Save the profile:
   ```bash
   scout-tools data save-profile --json <profile-json-file>
   ```

### 4. Check Profile Hash

If `data/candidate-profile.json` already exists and the user did NOT request a refresh:

```bash
scout-tools data check-profile-hash
```

If the hash doesn't match (resume was modified since last parse), suggest running `refresh-profile` to update the profile.

### 5. Verify Directory Structure

Ensure these directories exist (create if missing):
- `input/`
- `data/`
- `output/`
- `output/resumes/`
- `output/cover-letters/`
- `output/analysis/`
- `output/interview-prep/`

### 6. Display Setup Summary

Present:
- Config status (found / created)
- Base resume status (found / missing)
- Profile status (current / stale / created)
- Candidate name and target roles
- Configured locations
- Directory structure status
- Suggested next steps:
  - If new setup: "Run `/scout-companies` to start finding companies"
  - If profile refreshed: "Profile updated. Your existing analyses and resumes are unaffected."
