from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.state_models import GameState
from src.agents.lore_agent import LoreAgentInput
from src.agents.npc_agent import NPCAgentInput
from src.agents.quest_agent import QuestAgentInput

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORLD_PATH = PROJECT_ROOT / "data" / "world" / "world_state.json"
NPC_PATH = PROJECT_ROOT / "data" / "npcs" / "npc_data.json"
QUEST_PATH = PROJECT_ROOT / "data" / "quests" / "quest_data.json"

_world_cache: Optional[Dict[str, Any]] = None
_npc_cache: Optional[Dict[str, Any]] = None
_quest_cache: Optional[Dict[str, Any]] = None


def _load_world_data() -> Dict[str, Any]:
    global _world_cache
    if _world_cache is None:
        _world_cache = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    return _world_cache


def _load_npc_data() -> Dict[str, Any]:
    global _npc_cache
    if _npc_cache is None:
        _npc_cache = json.loads(NPC_PATH.read_text(encoding="utf-8"))
    return _npc_cache


def _load_quest_data() -> Dict[str, Any]:
    global _quest_cache
    if _quest_cache is None:
        _quest_cache = json.loads(QUEST_PATH.read_text(encoding="utf-8"))
    return _quest_cache


def get_location_data(location_key: str) -> Optional[Dict[str, Any]]:
    """Look up a location by id or display name. The seed uses display names, state uses ids."""
    world = _load_world_data()
    if not location_key:
        return None
    key_lower = location_key.lower()
    for loc in world.get("locations", []):
        if loc.get("id", "").lower() == key_lower:
            return loc
        if loc.get("name", "").lower() == key_lower:
            return loc
    return None


def get_world_summary() -> str:
    return _load_world_data().get("world_summary", "")


def get_npc_data(npc_id: str) -> Optional[Dict[str, Any]]:
    npc_data = _load_npc_data()
    for npc in npc_data.get("npcs", []):
        if npc.get("id") == npc_id:
            return npc
    return None


def get_npcs_at_location(state: GameState, location_key: str) -> List[str]:
    key_lower = (location_key or "").lower()
    return [
        npc_id
        for npc_id, npc_state in state.canonical.npc_states.items()
        if (npc_state.location or "").lower() == key_lower
    ]


def get_quest_data(quest_id: str) -> Optional[Dict[str, Any]]:
    quest_data = _load_quest_data()
    for quest in quest_data.get("quests", []):
        if quest.get("id") == quest_id:
            return quest
    return None


def build_lore_agent_input(state: GameState) -> LoreAgentInput:
    location_key = state.canonical.location
    location_data = get_location_data(location_key) or {}

    world_summary = get_world_summary()
    if not world_summary:
        world_summary = location_data.get("description", "")

    active_quest_summaries = [
        f"{q.name} ({q.status})"
        for q in state.canonical.active_quests
        if q.status != "not_started"
    ]
    if not active_quest_summaries:
        active_quest_summaries = [
            f"{q.name} ({q.status})" for q in state.canonical.active_quests
        ]

    return LoreAgentInput(
        player_action=state.turn.player_action,
        current_scene=state.canonical.current_scene,
        location=location_key,
        world_summary=world_summary,
        relevant_facts=location_data.get("relevant_facts", []),
        active_quest_summaries=active_quest_summaries,
    )


def build_npc_agent_input(state: GameState, npc_id: str) -> NPCAgentInput:
    npc_state = state.canonical.npc_states.get(npc_id)
    if npc_state is None:
        raise ValueError(f"No NPC with id '{npc_id}' in current state.")

    npc_seed = get_npc_data(npc_id) or {}

    return NPCAgentInput(
        player_action=state.turn.player_action,
        npc_name=npc_state.name,
        npc_role=npc_seed.get("role", "unknown"),
        npc_personality=npc_seed.get("personality", []),
        npc_goals=npc_state.goals or npc_seed.get("goals", []),
        npc_disposition=npc_state.disposition or npc_seed.get("disposition", "neutral"),
        current_scene=state.canonical.current_scene,
        relationship_summary=npc_seed.get("relationship_summary"),
        relevant_memory=npc_seed.get("knowledge", []),
    )


def build_quest_agent_input(state: GameState) -> QuestAgentInput:
    active_quest_summaries = [
        f"{q.name}: {q.status}" for q in state.canonical.active_quests
    ]
    completed_objectives = [
        obj.description
        for q in state.canonical.active_quests
        for obj in q.objectives
        if obj.completed
    ]
    recent_player_choices = [
        e.summary
        for e in state.canonical.recent_events[-5:]
        if e.event_type in ("player_choice", "branch_taken")
    ]

    location_key = state.canonical.location
    npcs_here = get_npcs_at_location(state, location_key)
    npc_names = [
        state.canonical.npc_states[nid].name
        for nid in npcs_here
        if nid in state.canonical.npc_states
    ]
    npc_context = f"NPCs present: {', '.join(npc_names)}" if npc_names else None

    return QuestAgentInput(
        player_action=state.turn.player_action,
        current_scene=state.canonical.current_scene,
        active_quest_summaries=active_quest_summaries,
        completed_objectives=completed_objectives,
        recent_player_choices=recent_player_choices,
        world_context=state.canonical.current_scene,
        npc_context=npc_context,
    )
