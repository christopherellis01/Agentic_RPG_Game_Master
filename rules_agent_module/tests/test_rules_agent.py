from __future__ import annotations

import importlib.util
from pathlib import Path


RULES_AGENT_PATH = Path(__file__).resolve().parents[1] / "src" / "agents" / "rules_agent.py"
spec = importlib.util.spec_from_file_location("standalone_rules_agent", RULES_AGENT_PATH)
rules_agent = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rules_agent)

resolve_action = rules_agent.resolve_action


def test_attack():
    result = resolve_action("attack goblin", {"enemy_hp": 20})
    assert result["action_type"] == "combat"


def test_dialogue():
    result = resolve_action("persuade guard", {"enemy_hp": 20})
    assert result["action_type"] == "dialogue"


def test_exploration():
    result = resolve_action("search room", {"enemy_hp": 20})
    assert result["action_type"] == "exploration"


def test_unknown():
    result = resolve_action("dance", {"enemy_hp": 20})
    assert result["outcome"] == "failure"


# NEW TESTS

def test_attack_with_state():
    state = {"enemy_hp": 20}
    result = resolve_action("attack goblin", state)

    assert "new_enemy_hp" in result["consequence"]


def test_output_structure():
    result = resolve_action("attack goblin", {"enemy_hp": 20})

    assert isinstance(result, dict)
    assert "action_type" in result
    assert "outcome" in result
    assert "reason" in result
    assert "consequence" in result


def test_case_insensitivity():
    result = resolve_action("ATTACK GOBLIN", {"enemy_hp": 20})
    assert result["action_type"] == "combat"
