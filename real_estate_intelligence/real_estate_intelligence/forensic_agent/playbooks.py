"""Forensic Diligence Playbooks Loader & Cache.

Loads and strips YAML frontmatter from `.agents/skills/*/SKILL.md` playbooks,
providing verified institutional instructions for the coordinator and synthesizer.
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional

_PLAYBOOK_CACHE: Dict[str, str] = {}

# Map intent / playbook keys to directory names
PLAYBOOK_DIR_MAP = {
    "due_diligence": "buyer-due-diligence",
    "buyer_due_diligence": "buyer-due-diligence",
    "pilot_auditor": "pilot-forensic-auditor",
    "pilot_forensic_auditor": "pilot-forensic-auditor",
    "market_analyst": "market-screening-analyst",
    "market_screening_analyst": "market-screening-analyst",
}


def _find_skills_root() -> Optional[Path]:
    """Find the .agents/skills directory across potential repository roots."""
    # Try relative to current working directory
    cwd_path = Path.cwd() / ".agents" / "skills"
    if cwd_path.is_dir():
        return cwd_path

    # Try walking up from this file's location
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = curr / ".agents" / "skills"
        if candidate.is_dir():
            return candidate
        curr = curr.parent

    return None


def strip_yaml_frontmatter(content: str) -> str:
    """Remove YAML frontmatter enclosed by '---' from markdown content."""
    if not content:
        return ""
    # Strip opening frontmatter if present
    return re.sub(r"^---\r?\n.*?\r?\n---\r?\n", "", content, flags=re.DOTALL).strip()


def load_playbook(name: str) -> str:
    """Load and cache a stripped playbook by key name."""
    canonical_key = name.lower().replace("-", "_").strip()
    if canonical_key in _PLAYBOOK_CACHE:
        return _PLAYBOOK_CACHE[canonical_key]

    dir_name = PLAYBOOK_DIR_MAP.get(canonical_key, canonical_key.replace("_", "-"))
    skills_root = _find_skills_root()
    if not skills_root:
        return ""

    file_path = skills_root / dir_name / "SKILL.md"
    if not file_path.is_file():
        return ""

    try:
        raw_text = file_path.read_text(encoding="utf-8")
        stripped = strip_yaml_frontmatter(raw_text)
        _PLAYBOOK_CACHE[canonical_key] = stripped
        return stripped
    except Exception:
        return ""


def get_playbook_instructions(
    intent: Optional[str] = None,
    data_tier: Optional[str] = None,
) -> str:
    """Retrieve combined or intent-specific playbook guidance.

    Prioritizes:
    - 'pilot_forensic_auditor' for pilot_deep tier or forensic audit intent.
    - 'buyer_due_diligence' for standard statutory due diligence and comparisons.
    """
    if intent and "market" in intent.lower():
        market_guide = load_playbook("market_analyst")
        if market_guide:
            return market_guide

    if data_tier == "pilot_deep" or (intent and "audit" in intent.lower()):
        pilot_guide = load_playbook("pilot_forensic_auditor")
        dd_guide = load_playbook("buyer_due_diligence")
        return f"{pilot_guide}\n\n---\n\n{dd_guide}" if pilot_guide else dd_guide

    dd_guide = load_playbook("buyer_due_diligence")
    if dd_guide:
        return dd_guide

    return load_playbook("pilot_forensic_auditor") or ""
