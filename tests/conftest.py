"""Shared test fixtures for Talent Scout tests."""

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from data_store import DataStore
from pipeline_store import PipelineStore


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "research").mkdir()
    return data_dir


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Create a temporary output directory structure."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    for subdir in ("resumes", "cover-letters", "analysis", "interview-prep"):
        (output_dir / subdir).mkdir()
    return output_dir


@pytest.fixture
def tmp_input_dir(tmp_path):
    """Create a temporary input directory with a base resume."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "base-resume.md").write_text("# Test Resume\n\nTest content.")
    return input_dir


@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration dictionary."""
    return {
        "user": {
            "name": "Test User",
            "email": "test@example.com",
            "linkedin_url": "https://linkedin.com/in/test",
            "base_resume_path": str(tmp_path / "input" / "base-resume.md"),
        },
        "preferences": {
            "locations": ["Palo Alto, CA"],
            "include_remote": True,
            "roles": ["Engineering Manager", "Software Manager"],
            "min_company_size": 100,
            "prefer_public_companies": True,
            "companies_per_location": 15,
            "output_format": "pdf",
            "pipeline": {
                "follow_up_days": 7,
                "follow_up_reminder_days": [7, 14],
                "auto_ghost_days": 30,
            },
        },
        "seeds": {
            "include": str(tmp_path / "input" / "target-companies.json"),
            "exclude": str(tmp_path / "input" / "excluded-companies.json"),
        },
        "target_companies": [],
        "excluded_companies": [],
    }


@pytest.fixture
def mock_claude_client():
    """Create a mock Claude client that returns predictable responses."""
    client = MagicMock()
    client.complete.return_value = "Mock response"
    client.complete_json.return_value = {}
    client.get_token_usage.return_value = {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    return client


@pytest.fixture
def data_store(test_config, tmp_data_dir, monkeypatch):
    """Create a DataStore using temporary directories."""
    store = DataStore(test_config)
    monkeypatch.setattr(store, "data_dir", tmp_data_dir)
    store._job_index = None
    return store


@pytest.fixture
def pipeline_store(test_config, tmp_data_dir, monkeypatch):
    """Create a PipelineStore using temporary directories."""
    store = PipelineStore(test_config)
    monkeypatch.setattr(store, "data_dir", tmp_data_dir)
    monkeypatch.setattr(store, "_file", tmp_data_dir / "pipeline.json")
    return store


@pytest.fixture
def sample_job():
    """Create a sample job dictionary."""
    return {
        "id": "JOB-TESTCO-ABC123",
        "company": "TestCo",
        "title": "Engineering Manager",
        "location": "Palo Alto, CA",
        "location_type": "palo-alto-ca",
        "url": "https://testco.com/jobs/123",
        "description": "We are looking for an Engineering Manager...",
        "source": "discovered",
        "match_score": 85,
        "key_skills": ["leadership", "python", "distributed systems"],
        "date_posted": "2026-01-15T00:00:00Z",
        "requirements_summary": "5+ years engineering management experience",
    }


@pytest.fixture
def sample_job_2():
    """Create a second sample job dictionary."""
    return {
        "id": "JOB-ACME-DEF456",
        "company": "Acme Corp",
        "title": "Director of Engineering",
        "location": "Remote",
        "location_type": "remote",
        "url": "https://acme.com/jobs/456",
        "description": "Acme Corp is hiring a Director of Engineering...",
        "source": "imported",
        "match_score": 72,
        "key_skills": ["management", "strategy", "cloud"],
        "date_posted": "2026-01-20T00:00:00Z",
    }


@pytest.fixture
def sample_company():
    """Create a sample company dictionary."""
    return {
        "name": "TestCo",
        "website": "https://testco.com",
        "hq_location": "Palo Alto, CA",
        "industry": "Enterprise Software",
        "employee_count": "500-1000",
        "public": True,
        "priority_score": 85,
        "notes": "Strong engineering culture, growing data team.",
    }


@pytest.fixture
def sample_analysis():
    """Create a sample job analysis dictionary."""
    return {
        "job_summary": {
            "title": "Engineering Manager",
            "company": "TestCo",
            "experience_required": "5+ years",
            "role_archetype": "engineering_management",
        },
        "match_assessment": {
            "overall_score": 85,
            "strengths": ["Leadership experience", "Technical depth"],
            "gaps": ["Specific domain experience"],
            "domain_connections": [],
        },
        "resume_recommendations": {
            "positioning_strategy": "Emphasize technical leadership",
            "keywords_to_include": ["engineering management", "team building"],
        },
        "cover_letter_points": [],
        "interview_prep": {},
    }


@pytest.fixture
def sample_profile():
    """Create a sample candidate profile."""
    return {
        "version": "1.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "source_resume_hash": "abc123",
        "identity": {
            "name": "Test User",
            "email": "test@example.com",
            "location": "Palo Alto, CA",
        },
        "summary": "Experienced engineering leader.",
        "experience": [
            {
                "company": "Previous Corp",
                "title": "Engineering Manager",
                "start_date": "2020",
                "end_date": "Present",
                "highlights": ["Led team of 10"],
                "skills_used": ["python", "leadership"],
            }
        ],
        "skills": {
            "technical": ["Python", "AWS", "Distributed Systems"],
            "leadership": ["Team Building", "Strategic Planning"],
            "domains": ["FinTech", "SaaS"],
        },
        "education": [],
        "preferences": {
            "target_roles": ["Engineering Manager"],
            "locations": ["Palo Alto, CA"],
            "include_remote": True,
        },
        "learned_preferences": {},
    }
