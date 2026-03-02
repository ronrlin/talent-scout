"""Resume Editor — programmatic edit application for resume improvement.

Extracted from resume_generator.py. Contains the Phase 2 logic:
exact-match replacement, fuzzy replacement, bullet addition/removal,
and Claude fallback for edits that string matching can't resolve.
"""

import re

from claude_client import ClaudeClient


def apply_replacement(resume: str, current_text: str, proposed_text: str) -> str | None:
    """Apply an exact string replacement. Returns None if not found."""
    if not current_text or current_text not in resume:
        return None
    return resume.replace(current_text, proposed_text, 1)


def apply_fuzzy_replacement(
    resume: str, current_text: str, proposed_text: str
) -> str | None:
    """Apply replacement with normalized whitespace matching."""
    if not current_text:
        return None

    def normalize(text: str) -> str:
        return " ".join(text.split())

    normalized_current = normalize(current_text)
    lines = resume.split("\n")
    rebuilt = []
    found = False

    i = 0
    while i < len(lines):
        if not found:
            # Try single line match
            if normalize(lines[i]) == normalized_current:
                leading = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                rebuilt.append(leading + proposed_text.strip())
                found = True
                i += 1
                continue

            # Try matching the line content (stripping markdown bullet prefix)
            line_content = lines[i].lstrip()
            if line_content.startswith("- "):
                line_content = line_content[2:]
            current_content = current_text.lstrip()
            if current_content.startswith("- "):
                current_content = current_content[2:]

            if normalize(line_content) == normalize(current_content):
                leading = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                if lines[i].lstrip().startswith("- "):
                    prefix = leading + "- "
                    new_text = proposed_text.strip()
                    if new_text.startswith("- "):
                        new_text = new_text[2:]
                    rebuilt.append(prefix + new_text)
                else:
                    rebuilt.append(leading + proposed_text.strip())
                found = True
                i += 1
                continue

        rebuilt.append(lines[i])
        i += 1

    if found:
        return "\n".join(rebuilt)
    return None


def apply_addition(resume: str, edit: dict) -> str | None:
    """Insert a new bullet after the specified target location."""
    target = edit.get("target", "")
    proposed_text = edit.get("proposed_text", "")

    if not proposed_text:
        return None

    match = re.search(r"after bullet (\d+)", target, re.IGNORECASE)
    company_match = re.match(r"^(.+?),\s*after", target, re.IGNORECASE)

    if not match:
        return None

    bullet_num = int(match.group(1))
    company_hint = company_match.group(1).strip() if company_match else ""

    lines = resume.split("\n")
    result_lines = []
    in_target_section = False
    bullet_count = 0
    inserted = False

    for i, line in enumerate(lines):
        result_lines.append(line)

        if company_hint and company_hint.lower() in line.lower() and (
            line.startswith("#") or line.startswith("**")
        ):
            in_target_section = True
            bullet_count = 0
            continue

        if in_target_section and not inserted and (
            line.startswith("### ") or line.startswith("## ")
        ) and bullet_count > 0:
            in_target_section = False

        if in_target_section and line.lstrip().startswith("- "):
            bullet_count += 1
            if bullet_count == bullet_num and not inserted:
                new_bullet = proposed_text.strip()
                if not new_bullet.startswith("- "):
                    new_bullet = "- " + new_bullet
                result_lines.append(new_bullet)
                inserted = True

    if inserted:
        return "\n".join(result_lines)
    return None


def apply_removal(resume: str, current_text: str) -> str | None:
    """Remove a bullet from the resume."""
    if not current_text:
        return None

    if current_text in resume:
        result = resume.replace(current_text, "", 1)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def normalize(text: str) -> str:
        return " ".join(text.split())

    normalized_target = normalize(current_text)
    lines = resume.split("\n")
    result_lines = []
    found = False

    for line in lines:
        if not found and normalize(line) == normalized_target:
            found = True
            continue
        result_lines.append(line)

    if found:
        return "\n".join(result_lines)
    return None


def apply_edits_via_claude(
    client: ClaudeClient, resume: str, failed_edits: list[tuple[int, dict]]
) -> str | None:
    """Fallback: use Claude to apply edits that string matching couldn't handle."""
    if not failed_edits:
        return None

    edit_instructions = []
    for i, edit in failed_edits:
        edit_type = edit.get("edit_type", "replace")
        target = edit.get("target", "")
        current_text = edit.get("current_text", "")
        proposed_text = edit.get("proposed_text", "")

        if edit_type == "replace":
            edit_instructions.append(
                f"EDIT {i+1} [{edit_type.upper()}]: In {target}, "
                f"find text similar to: \"{current_text}\" "
                f"and replace it with: \"{proposed_text}\""
            )
        elif edit_type == "add":
            edit_instructions.append(
                f"EDIT {i+1} [ADD]: In {target}, "
                f"add this bullet: \"{proposed_text}\""
            )
        elif edit_type == "remove":
            edit_instructions.append(
                f"EDIT {i+1} [REMOVE]: In {target}, "
                f"remove the bullet: \"{current_text}\""
            )

    response = client.complete(
        system="""Apply the specified edits to the resume. Change ONLY what is described in the edits. Do not modify any other part of the resume. Preserve all formatting, structure, and whitespace exactly. Output ONLY the modified resume in Markdown.""",
        user=f"""Apply these specific edits to the resume:

{chr(10).join(edit_instructions)}

RESUME:
{resume}""",
        max_tokens=4096,
    )

    return response if response else None
