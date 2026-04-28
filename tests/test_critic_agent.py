"""
Tests for the Critic Agent.

Covers:
  - Deterministic checks (no LLM): invalid combat, quest duplication, disposition mismatch
  - Fallback output when critic is unavailable
  - API integration: critic payload appears in /turn response
  - API integration: critic blocks patches on reject (structural guard)
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from src.agents.critic_agent import (
    CriticInput,
    CriticOutput,
    CriticIssue,
    _run_deterministic_checks,
    fallback_critic_output,
    _needs_llm_check,
)


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------

def test_flags_combat_against_dead_enemy():
    critic_input = CriticInput(
        player_action="I attack the goblin.",
        route="combat",
        current_location="oakshade_village",
        current_scene="The inn.",
        combatant_states={
            "goblin": {"name": "Goblin", "hp": 0, "max_hp": 15, "is_hostile": True}
        },
        rules_proposal={
            "outcome": "success",
            "damage_dealt": 10,
            "damage_taken": 0,
            "mechanical_summary": "Attack lands.",
            "proposed_state_changes": [],
        },
    )
    issues = _run_deterministic_checks(critic_input)
    assert any(i.issue_type == "invalid_combat" for i in issues)
    assert any(i.severity == "warning" for i in issues)


def test_no_combat_issue_when_enemy_alive():
    critic_input = CriticInput(
        player_action="I attack the goblin.",
        route="combat",
        current_location="oakshade_village",
        current_scene="The inn.",
        combatant_states={
            "goblin": {"name": "Goblin", "hp": 10, "max_hp": 15, "is_hostile": True}
        },
        rules_proposal={
            "outcome": "success",
            "damage_dealt": 5,
            "damage_taken": 0,
            "mechanical_summary": "Attack lands.",
            "proposed_state_changes": [],
        },
    )
    issues = _run_deterministic_checks(critic_input)
    assert not any(i.issue_type == "invalid_combat" for i in issues)


def test_flags_already_complete_objective():
    critic_input = CriticInput(
        player_action="I complete the objective.",
        route="quest_progression",
        current_location="oakshade_village",
        current_scene="The village square.",
        quest_states=[
            {
                "quest_id": "q1",
                "name": "Find the scout",
                "status": "active",
                "objectives": [
                    {"objective_id": "obj_find_clue", "description": "Find a clue.", "completed": True}
                ],
            }
        ],
        quest_proposal={
            "progress_interpretation": "Player found the clue.",
            "objective_status_updates": ["obj_find_clue: completed"],
            "new_branches_or_hooks": [],
        },
    )
    issues = _run_deterministic_checks(critic_input)
    assert any(i.issue_type == "illegal_transition" for i in issues)


def test_no_objective_issue_when_incomplete():
    critic_input = CriticInput(
        player_action="I search for clues.",
        route="quest_progression",
        current_location="oakshade_village",
        current_scene="The village square.",
        quest_states=[
            {
                "quest_id": "q1",
                "name": "Find the scout",
                "status": "active",
                "objectives": [
                    {"objective_id": "obj_find_clue", "description": "Find a clue.", "completed": False}
                ],
            }
        ],
        quest_proposal={
            "progress_interpretation": "Player found the clue.",
            "objective_status_updates": ["obj_find_clue: completed"],
            "new_branches_or_hooks": [],
        },
    )
    issues = _run_deterministic_checks(critic_input)
    assert not any(i.issue_type == "illegal_transition" for i in issues)


def test_flags_disposition_tone_mismatch():
    critic_input = CriticInput(
        player_action="I talk to the guard.",
        route="dialogue",
        current_location="oakshade_village",
        current_scene="The gate.",
        npc_disposition="hostile",
        npc_proposal={
            "speech": "Welcome, friend!",
            "emotional_tone": "friendly and welcoming",
            "intent": "Help the player.",
            "proposed_social_consequences": [],
        },
    )
    issues = _run_deterministic_checks(critic_input)
    assert any(i.issue_type == "npc_behavior_violation" for i in issues)


# ---------------------------------------------------------------------------
# LLM check gate
# ---------------------------------------------------------------------------

def test_llm_check_needed_when_npc_proposal():
    critic_input = CriticInput(
        player_action="I talk to Mara.",
        route="dialogue",
        current_location="oakshade_village",
        current_scene="The inn.",
        npc_proposal={"speech": "Hello.", "emotional_tone": "neutral", "intent": "Greet player."},
    )
    assert _needs_llm_check(critic_input) is True


def test_llm_check_not_needed_for_pure_combat():
    critic_input = CriticInput(
        player_action="I attack the goblin.",
        route="combat",
        current_location="oakshade_village",
        current_scene="Combat area.",
        rules_proposal={"damage_dealt": 5, "outcome": "success", "mechanical_summary": "Hit."},
    )
    assert _needs_llm_check(critic_input) is False


# ---------------------------------------------------------------------------
# Fallback output
# ---------------------------------------------------------------------------

def test_fallback_critic_output_approves():
    output = fallback_critic_output()
    assert output.verdict == "approve"
    assert len(output.issues) == 1
    assert output.issues[0].severity == "info"


# ---------------------------------------------------------------------------
# API integration: critic payload present in /turn response
# ---------------------------------------------------------------------------

def test_turn_response_includes_critic_payload():
    import src.api as api
    importlib.reload(api)

    client = TestClient(api.app)
    client.post("/reset")

    response = client.post(
        "/turn",
        json={
            "player_action": "I attack the goblin with my sword.",
            "target_npc_id": None,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Critic payload must be present
    assert "critic" in data
    assert data["critic"] is not None
    assert "verdict" in data["critic"]
    assert data["critic"]["verdict"] in ("approve", "warn", "reject")

    # Critic must appear in agent_activity
    activity_names = [item["name"] for item in data["agent_activity"]]
    assert "critic" in activity_names


def test_combat_turn_critic_approves_and_patches_applied():
    """
    For a standard attack against a living goblin, the critic should approve
    and the goblin HP should decrease.
    """
    import src.api as api
    importlib.reload(api)

    client = TestClient(api.app)
    client.post("/reset")

    initial_state = client.get("/state").json()
    initial_hp = initial_state["combatants"][0]["hp"]

    response = client.post(
        "/turn",
        json={
            "player_action": "I attack the goblin with my sword.",
            "target_npc_id": None,
        },
    )

    assert response.status_code == 200
    data = response.json()

    damage_dealt = data["rules"]["damage_dealt"]
    expected_hp = max(initial_hp - damage_dealt, 0)

    state_after = client.get("/state").json()
    goblin_after = state_after["combatants"][0]

    # Critic should not have rejected; HP should update
    assert data["critic"]["verdict"] in ("approve", "warn")
    assert goblin_after["hp"] == expected_hp


def test_critic_entry_in_activity_has_summary():
    import src.api as api
    importlib.reload(api)

    client = TestClient(api.app)
    client.post("/reset")

    response = client.post(
        "/turn",
        json={"player_action": "I look around the inn.", "target_npc_id": None},
    )

    assert response.status_code == 200
    data = response.json()

    critic_activity = next(
        (item for item in data["agent_activity"] if item["name"] == "critic"), None
    )
    assert critic_activity is not None
    assert critic_activity["summary"]  # non-empty string
