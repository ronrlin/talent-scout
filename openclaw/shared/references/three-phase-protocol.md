# Three-Phase Improvement Protocol

Used by: `scout-resume` (improve mode, `--improve`)

## Why Three Phases?

Improving an existing resume is fundamentally different from generating one. The document already has structure, specific content, and a narrative flow. Wholesale rewriting risks losing carefully crafted elements. Instead, surgical edits — targeted replacements, additions, and removals — improve alignment while preserving what already works.

The three-phase protocol separates planning, execution, and verification.

## How It Works

### Phase 1: Edit Plan Generation
An expert resume strategist analyzes the current resume against the job description, base resume, and analysis to propose 3-8 surgical edits. Each edit is one of:

- **replace** — change existing bullet text or summary
- **add** — insert a new bullet grounded in the base resume or additional context
- **remove** — delete a distracting or low-leverage bullet
- **reorder** — move a bullet within a role for better emphasis

The edit plan includes:
- `strategic_summary` — 3-5 bullets explaining the major positioning shifts
- `edit_plan` — array of specific edits with target, current_text, proposed_text, rationale, and source_evidence
- `unchanged_rationale` — why remaining bullets are already strong
- `remaining_gaps` — gaps that cannot be addressed without fabrication

### Phase 2: Programmatic Application
Edits are applied via `scout-tools edit apply`, which uses:

1. **Exact string matching** — find `current_text` in the resume and replace with `proposed_text`
2. **Fuzzy matching fallback** — normalized whitespace matching, bullet prefix handling

If any edits fail programmatic application (string not found), they are applied manually with full document context.

### Phase 3: Credibility Audit
An independent auditor reviews ONLY the changed lines for:

1. **JD parroting** — phrases too close to the job description
2. **Credibility** — every claim must trace to the base resume or additional context
3. **Voice mismatch** — edited lines must match the tone of surrounding unchanged content
4. **Inflation** — overstated scope, impact, or responsibility

For each edit, the auditor returns:
- **pass** — the edit is credible and natural
- **soften** — provides a revised version that fixes the issue
- **revert** — the edit should be rolled back entirely

Special handling for Professional Summary: the summary is a positioning statement. Reframing emphasis for the target role is valid and should not be reverted simply because it differs from the base resume's framing.

## Guardrails

- **Proportion test**: Edits should modify no more than ~25% of total resume content
- **Origin test**: Every fact must trace to the base resume or additional context
- **Interview test**: The candidate could explain every changed line naturally
- **Voice test**: Language must match the surrounding tone and specificity
