"""Shared constants for Elitza Agent."""

import os
from pathlib import Path


def get_elitza_home() -> Path:
    """Return the Elitza home directory (default: ~/.elitza)."""
    val = os.environ.get("ELITZA_HOME", "").strip()
    if val:
        return Path(val)
    return Path.home() / ".elitza"


def get_config_path() -> Path:
    return get_elitza_home() / "config.yaml"


def get_skills_dir() -> Path:
    return get_elitza_home() / "skills"


def get_env_path() -> Path:
    return get_elitza_home() / ".env"


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
