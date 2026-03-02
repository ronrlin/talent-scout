#!/usr/bin/env python3
"""Unified CLI for Talent Scout data operations.

Used by OpenClaw skills to safely read/write data without direct file access.
All output is JSON to stdout; errors go to stderr with non-zero exit code.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Resolve project root (3 levels up: scripts → shared → openclaw → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config_loader import load_config, classify_job_location
from data_store import DataStore
from pipeline_store import PipelineStore


# ============================================================================
# Helpers
# ============================================================================

_config = None
_data_store = None
_pipeline_store = None


def _get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _get_data_store():
    global _data_store
    if _data_store is None:
        _data_store = DataStore(_get_config())
    return _data_store


def _get_pipeline_store():
    global _pipeline_store
    if _pipeline_store is None:
        _pipeline_store = PipelineStore(_get_config())
    return _pipeline_store


def _output(data):
    """JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _error(msg):
    """Error to stderr, exit 1."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _read_json(arg):
    """Read JSON from file path or stdin (if arg is '-')."""
    if arg == "-":
        return json.load(sys.stdin)
    return json.loads(Path(arg).read_text())


# ============================================================================
# Data subcommands
# ============================================================================

def cmd_data_get_job(args):
    ds = _get_data_store()
    job = ds.get_job(args.id)
    if job is None:
        _error(f"job not found: {args.id}")
    _output(job)


def cmd_data_save_job(args):
    ds = _get_data_store()
    job = _read_json(args.json)
    location = args.location if args.location else None
    result = ds.save_job(job, location)
    _output({"saved": result, "job_id": job.get("id")})


def cmd_data_update_job(args):
    ds = _get_data_store()
    updates = _read_json(args.json)
    result = ds.update_job(args.id, updates)
    if not result:
        _error(f"job not found: {args.id}")
    _output({"updated": True, "job_id": args.id})


def cmd_data_list_jobs(args):
    ds = _get_data_store()
    location = args.location if args.location and args.location != "all" else None
    jobs = ds.get_jobs(
        location_slug=location,
        company=args.company,
        source=args.source,
    )
    _output(jobs)


def cmd_data_delete_job(args):
    ds = _get_data_store()
    job = ds.delete_job(args.id)
    if job is None:
        _error(f"job not found: {args.id}")
    _output(job)


def cmd_data_save_jobs(args):
    ds = _get_data_store()
    jobs = _read_json(args.json)
    count = ds.save_jobs(jobs, args.company)
    _output({"added": count})


def cmd_data_job_exists(args):
    ds = _get_data_store()
    exists = ds.job_exists(
        job_id=args.id,
        company=args.company,
        title=args.title,
    )
    _output({"exists": exists})


def cmd_data_record_deleted_job(args):
    ds = _get_data_store()
    job = _read_json(args.json)
    ds.record_deleted_job(job, args.reason)
    _output({"recorded": True})


def cmd_data_get_deleted_jobs(args):
    ds = _get_data_store()
    _output(ds.get_deleted_jobs())


def cmd_data_get_research(args):
    ds = _get_data_store()
    research = ds.get_research(args.slug)
    if research is None:
        _error(f"research not found: {args.slug}")
    _output(research)


def cmd_data_save_research(args):
    ds = _get_data_store()
    research = _read_json(args.json)
    ds.save_research(args.slug, research)
    _output({"saved": True, "slug": args.slug})


def cmd_data_get_companies(args):
    ds = _get_data_store()
    _output(ds.get_companies(args.location))


def cmd_data_save_companies(args):
    ds = _get_data_store()
    companies = _read_json(args.json)
    ds.save_companies(companies, args.location_slug, args.location)
    _output({"saved": True, "count": len(companies)})


def cmd_data_get_profile(args):
    ds = _get_data_store()
    profile = ds.get_profile()
    if profile is None:
        _error("no profile found")
    _output(profile)


def cmd_data_save_profile(args):
    ds = _get_data_store()
    profile = _read_json(args.json)
    ds.save_profile(profile)
    _output({"saved": True})


def cmd_data_get_learned_prefs(args):
    ds = _get_data_store()
    prefs = ds.get_learned_preferences()
    if prefs is None:
        _output({})
    else:
        _output(prefs)


def cmd_data_save_learned_prefs(args):
    ds = _get_data_store()
    prefs = _read_json(args.json)
    ds.save_learned_preferences(prefs)
    _output({"saved": True})


def cmd_data_get_corpus(args):
    ds = _get_data_store()
    corpus = ds.get_corpus()
    if corpus is None:
        _error("no corpus found")
    _output(corpus)


def cmd_data_save_corpus(args):
    ds = _get_data_store()
    corpus = _read_json(args.json)
    ds.save_corpus(corpus)
    _output({"saved": True})


def cmd_data_classify_location(args):
    config = _get_config()
    slug = classify_job_location(args.location, config)
    _output({"location": args.location, "slug": slug})


def cmd_data_check_profile_hash(args):
    ds = _get_data_store()
    profile = ds.get_profile()
    resume_path = PROJECT_ROOT / "input" / "base-resume.md"
    if not resume_path.exists():
        _error("base-resume.md not found")
    current_hash = hashlib.sha256(resume_path.read_bytes()).hexdigest()
    stored_hash = profile.get("source_hash") if profile else None
    _output({
        "current_hash": current_hash,
        "stored_hash": stored_hash,
        "changed": current_hash != stored_hash,
    })


def cmd_data_invalidate_index(args):
    ds = _get_data_store()
    ds.invalidate_index()
    _output({"invalidated": True})


# ============================================================================
# Pipeline subcommands
# ============================================================================

def cmd_pipeline_create(args):
    ps = _get_pipeline_store()
    entry = ps.create(args.id, args.trigger)
    _output(entry)


def cmd_pipeline_advance(args):
    ps = _get_pipeline_store()
    result = ps.advance(args.id, args.stage, args.trigger)
    if not result:
        _error(f"cannot advance {args.id} to {args.stage}")
    _output({"advanced": True, "job_id": args.id, "stage": args.stage})


def cmd_pipeline_set_status(args):
    ps = _get_pipeline_store()
    result = ps.set_status(args.id, args.stage, args.trigger)
    if not result:
        _error(f"cannot set status for {args.id}")
    _output({"set": True, "job_id": args.id, "stage": args.stage})


def cmd_pipeline_close(args):
    ps = _get_pipeline_store()
    result = ps.close(args.id, args.outcome, args.trigger)
    if not result:
        _error(f"cannot close {args.id} with outcome {args.outcome}")
    _output({"closed": True, "job_id": args.id, "outcome": args.outcome})


def cmd_pipeline_remove(args):
    ps = _get_pipeline_store()
    result = ps.remove(args.id)
    if not result:
        _error(f"job not in pipeline: {args.id}")
    _output({"removed": True, "job_id": args.id})


def cmd_pipeline_get(args):
    ps = _get_pipeline_store()
    entry = ps.get(args.id)
    if entry is None:
        _error(f"job not in pipeline: {args.id}")
    _output(entry)


def cmd_pipeline_get_all(args):
    ps = _get_pipeline_store()
    _output(ps.get_all())


def cmd_pipeline_get_by_status(args):
    ps = _get_pipeline_store()
    _output(ps.get_by_status(args.status))


def cmd_pipeline_get_history(args):
    ps = _get_pipeline_store()
    history = ps.get_history(args.id)
    if not history:
        _error(f"no history for {args.id}")
    _output(history)


def cmd_pipeline_get_stats(args):
    ps = _get_pipeline_store()
    _output(ps.get_stats())


def cmd_pipeline_record_artifact(args):
    ps = _get_pipeline_store()
    result = ps.record_artifact(args.id, args.type, args.path)
    if not result:
        _error(f"cannot record artifact for {args.id}")
    _output({"recorded": True, "job_id": args.id, "type": args.type})


def cmd_pipeline_add_note(args):
    ps = _get_pipeline_store()
    result = ps.add_note(args.id, args.note)
    if not result:
        _error(f"job not in pipeline: {args.id}")
    _output({"added": True, "job_id": args.id})


def cmd_pipeline_actionable(args):
    ps = _get_pipeline_store()
    ds = _get_data_store()
    jobs = ds.get_jobs()
    _output(ps.get_actionable(args.days, jobs))


def cmd_pipeline_overview(args):
    ps = _get_pipeline_store()
    _output({
        "applications": ps.get_all(),
        "stats": ps.get_stats(),
    })


# ============================================================================
# Convert subcommands
# ============================================================================

def cmd_convert_resume(args):
    from services.document_converter import convert_document
    md_path = Path(args.input_path)
    if not md_path.exists():
        _error(f"file not found: {md_path}")
    results = convert_document(md_path, "resume", args.format)
    _output({k: str(v) if v else None for k, v in results.items()})


def cmd_convert_cover_letter(args):
    from services.document_converter import convert_document
    md_path = Path(args.input_path)
    if not md_path.exists():
        _error(f"file not found: {md_path}")
    results = convert_document(md_path, "cover-letter", args.format)
    _output({k: str(v) if v else None for k, v in results.items()})


# ============================================================================
# Edit subcommands
# ============================================================================

def _apply_replacement(resume, current_text, proposed_text):
    """Apply an exact string replacement. Returns None if not found."""
    if not current_text or current_text not in resume:
        return None
    return resume.replace(current_text, proposed_text, 1)


def _apply_fuzzy_replacement(resume, current_text, proposed_text):
    """Apply replacement with normalized whitespace matching."""
    if not current_text:
        return None

    def normalize(text):
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


def _apply_addition(resume, edit):
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


def _apply_removal(resume, current_text):
    """Remove a bullet from the resume."""
    if not current_text:
        return None

    if current_text in resume:
        result = resume.replace(current_text, "", 1)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def normalize(text):
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


def cmd_edit_apply(args):
    resume_path = Path(args.resume)
    edits_path = Path(args.edits)
    if not resume_path.exists():
        _error(f"file not found: {resume_path}")
    if not edits_path.exists():
        _error(f"file not found: {edits_path}")

    resume = resume_path.read_text()
    edit_plan = json.loads(edits_path.read_text())
    edits = edit_plan.get("edit_plan", [])

    applied = []
    failed_edits = []

    for edit in edits:
        edit_type = edit.get("edit_type", "replace")
        target = edit.get("target", "")
        current_text = edit.get("current_text", "")
        proposed_text = edit.get("proposed_text", "")

        if edit_type == "replace":
            result = _apply_replacement(resume, current_text, proposed_text)
            if result is not None:
                resume = result
                applied.append({"target": target, "edit_type": "replace", "method": "exact"})
            else:
                result = _apply_fuzzy_replacement(resume, current_text, proposed_text)
                if result is not None:
                    resume = result
                    applied.append({"target": target, "edit_type": "replace", "method": "fuzzy"})
                else:
                    failed_edits.append({"target": target, "edit_type": "replace", "reason": "current_text not found"})

        elif edit_type == "add":
            result = _apply_addition(resume, edit)
            if result is not None:
                resume = result
                applied.append({"target": target, "edit_type": "add"})
            else:
                failed_edits.append({"target": target, "edit_type": "add", "reason": "could not find insertion point"})

        elif edit_type == "remove":
            result = _apply_removal(resume, current_text)
            if result is not None:
                resume = result
                applied.append({"target": target, "edit_type": "remove"})
            else:
                failed_edits.append({"target": target, "edit_type": "remove", "reason": "current_text not found"})

    _output({"resume": resume, "applied": applied, "failed_edits": failed_edits})


# ============================================================================
# Argparse setup
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="scout-tools",
        description="Unified CLI for Talent Scout data operations.",
    )
    subparsers = parser.add_subparsers(dest="group")

    # ---- data group ----
    data_parser = subparsers.add_parser("data", help="Data store operations")
    data_sub = data_parser.add_subparsers(dest="command")

    # data get-job
    p = data_sub.add_parser("get-job")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_data_get_job)

    # data save-job
    p = data_sub.add_parser("save-job")
    p.add_argument("--json", required=True, help="JSON file path or '-' for stdin")
    p.add_argument("--location", default=None)
    p.set_defaults(func=cmd_data_save_job)

    # data update-job
    p = data_sub.add_parser("update-job")
    p.add_argument("--id", required=True)
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_data_update_job)

    # data list-jobs
    p = data_sub.add_parser("list-jobs")
    p.add_argument("--location", default=None)
    p.add_argument("--company", default=None)
    p.add_argument("--source", default=None)
    p.set_defaults(func=cmd_data_list_jobs)

    # data delete-job
    p = data_sub.add_parser("delete-job")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_data_delete_job)

    # data save-jobs
    p = data_sub.add_parser("save-jobs")
    p.add_argument("--json", required=True)
    p.add_argument("--company", default=None)
    p.set_defaults(func=cmd_data_save_jobs)

    # data job-exists
    p = data_sub.add_parser("job-exists")
    p.add_argument("--id", default=None)
    p.add_argument("--company", default=None)
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_data_job_exists)

    # data record-deleted-job
    p = data_sub.add_parser("record-deleted-job")
    p.add_argument("--json", required=True)
    p.add_argument("--reason", default=None)
    p.set_defaults(func=cmd_data_record_deleted_job)

    # data get-deleted-jobs
    p = data_sub.add_parser("get-deleted-jobs")
    p.set_defaults(func=cmd_data_get_deleted_jobs)

    # data get-research
    p = data_sub.add_parser("get-research")
    p.add_argument("--slug", required=True)
    p.set_defaults(func=cmd_data_get_research)

    # data save-research
    p = data_sub.add_parser("save-research")
    p.add_argument("--slug", required=True)
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_data_save_research)

    # data get-companies
    p = data_sub.add_parser("get-companies")
    p.add_argument("--location", required=True)
    p.set_defaults(func=cmd_data_get_companies)

    # data save-companies
    p = data_sub.add_parser("save-companies")
    p.add_argument("--json", required=True)
    p.add_argument("--location-slug", required=True)
    p.add_argument("--location", required=True)
    p.set_defaults(func=cmd_data_save_companies)

    # data get-profile
    p = data_sub.add_parser("get-profile")
    p.set_defaults(func=cmd_data_get_profile)

    # data save-profile
    p = data_sub.add_parser("save-profile")
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_data_save_profile)

    # data get-learned-prefs
    p = data_sub.add_parser("get-learned-prefs")
    p.set_defaults(func=cmd_data_get_learned_prefs)

    # data save-learned-prefs
    p = data_sub.add_parser("save-learned-prefs")
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_data_save_learned_prefs)

    # data get-corpus
    p = data_sub.add_parser("get-corpus")
    p.set_defaults(func=cmd_data_get_corpus)

    # data save-corpus
    p = data_sub.add_parser("save-corpus")
    p.add_argument("--json", required=True)
    p.set_defaults(func=cmd_data_save_corpus)

    # data classify-location
    p = data_sub.add_parser("classify-location")
    p.add_argument("location")
    p.set_defaults(func=cmd_data_classify_location)

    # data check-profile-hash
    p = data_sub.add_parser("check-profile-hash")
    p.set_defaults(func=cmd_data_check_profile_hash)

    # data invalidate-index
    p = data_sub.add_parser("invalidate-index")
    p.set_defaults(func=cmd_data_invalidate_index)

    # ---- pipeline group ----
    pipe_parser = subparsers.add_parser("pipeline", help="Pipeline state operations")
    pipe_sub = pipe_parser.add_subparsers(dest="command")

    # pipeline create
    p = pipe_sub.add_parser("create")
    p.add_argument("--id", required=True)
    p.add_argument("--trigger", required=True)
    p.set_defaults(func=cmd_pipeline_create)

    # pipeline advance
    p = pipe_sub.add_parser("advance")
    p.add_argument("--id", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--trigger", required=True)
    p.set_defaults(func=cmd_pipeline_advance)

    # pipeline set-status
    p = pipe_sub.add_parser("set-status")
    p.add_argument("--id", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--trigger", required=True)
    p.set_defaults(func=cmd_pipeline_set_status)

    # pipeline close
    p = pipe_sub.add_parser("close")
    p.add_argument("--id", required=True)
    p.add_argument("--outcome", required=True)
    p.add_argument("--trigger", required=True)
    p.set_defaults(func=cmd_pipeline_close)

    # pipeline remove
    p = pipe_sub.add_parser("remove")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_pipeline_remove)

    # pipeline get
    p = pipe_sub.add_parser("get")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_pipeline_get)

    # pipeline get-all
    p = pipe_sub.add_parser("get-all")
    p.set_defaults(func=cmd_pipeline_get_all)

    # pipeline get-by-status
    p = pipe_sub.add_parser("get-by-status")
    p.add_argument("--status", required=True)
    p.set_defaults(func=cmd_pipeline_get_by_status)

    # pipeline get-history
    p = pipe_sub.add_parser("get-history")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_pipeline_get_history)

    # pipeline get-stats
    p = pipe_sub.add_parser("get-stats")
    p.set_defaults(func=cmd_pipeline_get_stats)

    # pipeline record-artifact
    p = pipe_sub.add_parser("record-artifact")
    p.add_argument("--id", required=True)
    p.add_argument("--type", required=True)
    p.add_argument("--path", required=True)
    p.set_defaults(func=cmd_pipeline_record_artifact)

    # pipeline add-note
    p = pipe_sub.add_parser("add-note")
    p.add_argument("--id", required=True)
    p.add_argument("--note", required=True)
    p.set_defaults(func=cmd_pipeline_add_note)

    # pipeline actionable
    p = pipe_sub.add_parser("actionable")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_pipeline_actionable)

    # pipeline overview
    p = pipe_sub.add_parser("overview")
    p.set_defaults(func=cmd_pipeline_overview)

    # ---- convert group ----
    convert_parser = subparsers.add_parser("convert", help="Document conversion")
    convert_sub = convert_parser.add_subparsers(dest="command")

    # convert resume
    p = convert_sub.add_parser("resume")
    p.add_argument("input_path")
    p.add_argument("format", choices=["pdf", "docx", "both"])
    p.set_defaults(func=cmd_convert_resume)

    # convert cover-letter
    p = convert_sub.add_parser("cover-letter")
    p.add_argument("input_path")
    p.add_argument("format", choices=["pdf", "docx", "both"])
    p.set_defaults(func=cmd_convert_cover_letter)

    # ---- edit group ----
    edit_parser = subparsers.add_parser("edit", help="Resume edit operations")
    edit_sub = edit_parser.add_subparsers(dest="command")

    # edit apply
    p = edit_sub.add_parser("apply")
    p.add_argument("resume", help="Path to resume markdown file")
    p.add_argument("edits", help="Path to edit plan JSON file")
    p.set_defaults(func=cmd_edit_apply)

    # ---- parse and dispatch ----
    args = parser.parse_args()

    if not args.group:
        parser.print_help()
        sys.exit(1)

    if not hasattr(args, "func"):
        # Print help for the group
        if args.group == "data":
            data_parser.print_help()
        elif args.group == "pipeline":
            pipe_parser.print_help()
        elif args.group == "convert":
            convert_parser.print_help()
        elif args.group == "edit":
            edit_parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        _error(str(e))


if __name__ == "__main__":
    main()
