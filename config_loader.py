"""Configuration loading utilities."""

import json
import os
from pathlib import Path


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from config.json."""
    if config_path is None:
        config_path = Path(__file__).parent / "config.json"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    # Load seed companies
    config["target_companies"] = _load_seed_file(config["seeds"]["include"])
    config["excluded_companies"] = _load_seed_file(config["seeds"]["exclude"])

    return config


def _load_seed_file(path: str) -> list[dict]:
    """Load a seed file (target or excluded companies)."""
    seed_path = Path(__file__).parent / path

    if not seed_path.exists():
        return []

    with open(seed_path) as f:
        data = json.load(f)

    return data.get("companies", [])


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it with: export ANTHROPIC_API_KEY=your-key"
        )
    return key
