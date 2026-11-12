"""Portable package locations and user-owned execution state."""
import json
import os
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
SKILL_ROOT = CODE_DIR.parent.parent
CODEX_DIR = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').resolve()
STATE_DIR = CODEX_DIR / 'frontend-policy'


def original_rules():
    policy = json.loads((SKILL_ROOT / 'references/policy.json').read_text(encoding='utf-8-sig'))
    return (SKILL_ROOT / policy['source_rules']).resolve()


def critic_config():
    installed = CODEX_DIR / 'agents/Critic.toml'
    return installed if installed.is_file() else SKILL_ROOT / 'assets/agents/Critic.toml'
