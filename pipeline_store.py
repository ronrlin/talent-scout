"""Pipeline state management for application lifecycle tracking.

Separate from DataStore by design — pipeline state lives in its own file
(data/pipeline.json) to support future swap to SQLite/document store and
multi-user support.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PIPELINE_STAGES = [
    "discovered",
    "researched",
    "resume_ready",
    "applied",
    "screening",
    "interviewing",
    "offer",
    "closed",
]

CLOSED_OUTCOMES = ["accepted", "rejected", "declined", "ghosted", "withdrawn"]

_STAGE_INDEX = {stage: i for i, stage in enumerate(PIPELINE_STAGES)}


class PipelineStore:
    """Manages application pipeline state in data/pipeline.json."""

    def __init__(self, config: dict):
        self.config = config
        self.data_dir = Path(__file__).parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self._file = self.data_dir / "pipeline.json"

    # =========================================================================
    # Core CRUD
    # =========================================================================

    def get(self, job_id: str) -> dict | None:
        """Get pipeline state for a job."""
        data = self._load()
        return data["applications"].get(job_id)

    def create(self, job_id: str, trigger: str) -> dict:
        """Create a pipeline entry with status=discovered.

        Idempotent — returns existing entry if already present.
        """
        data = self._load()

        if job_id in data["applications"]:
            return data["applications"][job_id]

        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "job_id": job_id,
            "status": "discovered",
            "created_at": now,
            "updated_at": now,
            "applied_at": None,
            "applied_via": None,
            "closed_at": None,
            "closed_outcome": None,
            "artifacts": {
                "analysis": None,
                "resume": None,
                "cover_letter": None,
                "interview_prep": None,
            },
            "notes": [],
            "history": [
                {
                    "stage": "discovered",
                    "timestamp": now,
                    "trigger": trigger,
                }
            ],
        }

        data["applications"][job_id] = entry
        self._save(data)
        return entry

    def advance(self, job_id: str, new_stage: str, trigger: str, **meta) -> bool:
        """Forward-only state transition.

        Returns False if job not in pipeline, stage is invalid,
        or new_stage is not ahead of current stage.
        """
        if new_stage not in _STAGE_INDEX:
            return False

        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return False

        current = entry["status"]
        if current not in _STAGE_INDEX:
            return False

        # Forward-only: new stage must be strictly ahead
        if _STAGE_INDEX[new_stage] <= _STAGE_INDEX[current]:
            return False

        now = datetime.now(timezone.utc).isoformat()
        entry["status"] = new_stage
        entry["updated_at"] = now

        history_entry = {"stage": new_stage, "timestamp": now, "trigger": trigger}
        history_entry.update(meta)
        entry["history"].append(history_entry)

        self._save(data)
        return True

    def set_status(self, job_id: str, stage: str, trigger: str, **meta) -> bool:
        """Manual override — can move to any stage (forward or backward)."""
        if stage not in _STAGE_INDEX:
            return False

        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return False

        now = datetime.now(timezone.utc).isoformat()
        entry["status"] = stage
        entry["updated_at"] = now

        # Store stage-specific metadata
        if stage == "applied":
            if "applied_via" in meta:
                entry["applied_via"] = meta.pop("applied_via")
            if "applied_at" not in meta:
                entry["applied_at"] = now
            else:
                entry["applied_at"] = meta.pop("applied_at")

        history_entry = {"stage": stage, "timestamp": now, "trigger": trigger}
        history_entry.update(meta)
        entry["history"].append(history_entry)

        self._save(data)
        return True

    def close(self, job_id: str, outcome: str, trigger: str) -> bool:
        """Set status=closed with an outcome."""
        if outcome not in CLOSED_OUTCOMES:
            return False

        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return False

        now = datetime.now(timezone.utc).isoformat()
        entry["status"] = "closed"
        entry["updated_at"] = now
        entry["closed_at"] = now
        entry["closed_outcome"] = outcome

        entry["history"].append({
            "stage": "closed",
            "timestamp": now,
            "trigger": trigger,
            "outcome": outcome,
        })

        self._save(data)
        return True

    # =========================================================================
    # Artifacts & Notes
    # =========================================================================

    def record_artifact(self, job_id: str, artifact_type: str, path: str) -> bool:
        """Track a generated file (analysis, resume, cover_letter, interview_prep)."""
        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return False

        if artifact_type not in entry.get("artifacts", {}):
            return False

        entry["artifacts"][artifact_type] = path
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return True

    def add_note(self, job_id: str, note: str) -> bool:
        """Add a timestamped note to a pipeline entry."""
        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return False

        entry["notes"].append({
            "text": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return True

    # =========================================================================
    # Queries
    # =========================================================================

    def get_by_status(self, status: str) -> list[dict]:
        """Get all entries at a given stage."""
        data = self._load()
        return [
            entry for entry in data["applications"].values()
            if entry["status"] == status
        ]

    def get_all(self) -> list[dict]:
        """Get all tracked applications."""
        data = self._load()
        return list(data["applications"].values())

    def get_history(self, job_id: str) -> list[dict]:
        """Get stage transition timeline for a job."""
        data = self._load()
        entry = data["applications"].get(job_id)
        if not entry:
            return []
        return entry.get("history", [])

    def get_actionable(self, follow_up_days: int = 7, jobs: list[dict] | None = None) -> dict:
        """Get grouped action items for scout next.

        Args:
            follow_up_days: Days after which applied jobs are considered overdue.
            jobs: Optional list of job dicts (from DataStore) for enrichment.
                  Used to get match_score for next_up sorting.

        Returns:
            Dict with keys: overdue, ready_to_act, in_progress, next_up
        """
        data = self._load()
        now = datetime.now(timezone.utc)

        # Build job lookup for enrichment
        job_lookup = {}
        if jobs:
            job_lookup = {j["id"]: j for j in jobs if "id" in j}

        overdue = []
        ready_to_act = []
        in_progress = []
        next_up = []

        for entry in data["applications"].values():
            status = entry["status"]
            job_id = entry["job_id"]

            # Enrich with job data
            enriched = {**entry}
            if job_id in job_lookup:
                job = job_lookup[job_id]
                enriched["company"] = job.get("company", "?")
                enriched["title"] = job.get("title", "?")
                enriched["match_score"] = job.get("match_score", 0)
            else:
                enriched.setdefault("company", "?")
                enriched.setdefault("title", "?")
                enriched.setdefault("match_score", 0)

            if status in ("applied", "screening", "interviewing"):
                updated = datetime.fromisoformat(entry["updated_at"])
                days_since = (now - updated).days
                enriched["days_since_update"] = days_since

                if days_since >= follow_up_days:
                    overdue.append(enriched)
                else:
                    in_progress.append(enriched)

            elif status == "resume_ready":
                ready_to_act.append(enriched)

            elif status in ("discovered", "researched"):
                next_up.append(enriched)

            # closed/offer entries are not actionable

        # Sort groups
        overdue.sort(key=lambda x: x.get("days_since_update", 0), reverse=True)
        ready_to_act.sort(key=lambda x: x.get("updated_at", ""))
        in_progress.sort(key=lambda x: x.get("updated_at", ""))
        next_up.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return {
            "overdue": overdue,
            "ready_to_act": ready_to_act,
            "in_progress": in_progress,
            "next_up": next_up,
        }

    def get_stats(self) -> dict:
        """Get conversion rates and time-in-stage stats (Phase 2)."""
        data = self._load()
        applications = data["applications"].values()

        stage_counts = {stage: 0 for stage in PIPELINE_STAGES}
        outcome_counts = {outcome: 0 for outcome in CLOSED_OUTCOMES}
        total = 0

        for entry in applications:
            total += 1
            status = entry["status"]
            if status in stage_counts:
                stage_counts[status] += 1
            if status == "closed":
                outcome = entry.get("closed_outcome", "")
                if outcome in outcome_counts:
                    outcome_counts[outcome] += 1

        return {
            "total": total,
            "by_stage": stage_counts,
            "by_outcome": outcome_counts,
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _load(self) -> dict:
        """Load pipeline data from disk."""
        if not self._file.exists():
            return {"applications": {}, "updated_at": None}

        with open(self._file) as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        """Write pipeline data to disk."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self._file, "w") as f:
            json.dump(data, f, indent=2)
