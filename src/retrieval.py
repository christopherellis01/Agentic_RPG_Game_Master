"""
Retrieval layer for the Agentic RPG Game Master.

This module bridges the gap between:
  - Christopher's canonical `GameState` (the live, validated runtime state)
  - the seed JSON files in `data/` (which carry richer authoring detail than
    the runtime state models currently preserve, e.g. personality traits,
    environmental_details, active_rumors)
  - the agent input models (`LoreAgentInput`, `NPCAgentInput`, `QuestAgentInput`)

Design choice:
The canonical `GameState` is the source of truth for anything that changes
during a session (quest status, NPC disposition, current location, inventory).
But the raw seed JSON holds authoring-time detail that the runtime state does
not yet model. So retrieval reads GameState first, then enriches from the
seed files for fields the runtime state doesn't carry.

Later, once the state models grow to hold those extra fields, this layer
can simply read from GameState and the JSON-reading helpers can go away.

Note on Christopher's data shapes:
  - `world_state.json` uses a LIST of locations (not a dict).
  - `world_state.json.starting_location` is a display NAME (e.g. "Oakshade Village"),
    not an id. So lookups need to tolerate either form.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.state_models import GameState
from src.agents.lore_agent import LoreAgentInput
from src.agents.npc_agent import NPCAgentInput
from src.agents.quest_agent import QuestAgentInput


# PROJECT PATHS — mirrors state_manager.py so we read the same seed files
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORLD_PATH = PROJECT_ROOT / "data" / "world" / "world_state.json"
NPC_PATH = PROJECT_ROOT / "data" / "npcs" / "npc_data.json"
QUEST_PATH = PROJECT_ROOT / "data" / "quests" / "quest_data.json"


# JSON LOADERS (cached so we don't re-read files on every turn)
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


# LOCATION LOOKUPS
# Christopher's world_state stores locations as a list, and his
# `starting_location` is a display name rather than an id. Accept either
# the id ("oakshade_village") or the display name ("Oakshade Village").
def get_location_data(location_key: str) -> Optional[Dict[str, Any]]:
    """Look up a location by id or by display name from the seed world data."""
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
    """Return the top-level world summary if present."""
    world = _load_world_data()
    return world.get("world_summary", "")


# NPC LOOKUPS
def get_npc_data(npc_id: str) -> Optional[Dict[str, Any]]:
    """Look up an NPC by id from the seed NPC data."""
    npc_data = _load_npc_data()
    for npc in npc_data.get("npcs", []):
        if npc.get("id") == npc_id:
            return npc
    return None


def get_npcs_at_location(state: GameState, location_key: str) -> List[str]:
    """
    Return ids of NPCs currently at the given location, according to live state.
    Accepts either a location id or display name.
    """
    # Live NPCState.location should be whatever state_manager stored, which in
    # Christopher's current code is the value of canonical.location. Compare
    # loosely so either id-vs-name form still matches.
    key_lower = (location_key or "").lower()
    return [
        npc_id
        for npc_id, npc_state in state.canonical.npc_states.items()
        if (npc_state.location or "").lower() == key_lower
    ]


# QUEST LOOKUPS
def get_quest_data(quest_id: str) -> Optional[Dict[str, Any]]:
    """Look up a quest by id from the seed quest data."""
    quest_data = _load_quest_data()
    for quest in quest_data.get("quests", []):
        if quest.get("id") == quest_id:
            return quest
    return None


# AGENT INPUT BUILDERS — the payoff. Orchestrator calls these to get
# ready-to-run agent inputs.

def build_lore_agent_input(state: GameState) -> LoreAgentInput:
    """Package everything the Lore Agent needs from current state + seed data."""
    location_key = state.canonical.location
    location_data = get_location_data(location_key) or {}

    # Prefer the location's own facts; fall back to top-level world summary.
    world_summary = get_world_summary()
    if not world_summary:
        world_summary = location_data.get("description", "")

    # active_quest_summaries pulled from live canonical state so they reflect
    # current status, not the seeded starting status.
    active_quest_summaries = [
        f"{q.name} ({q.status})"
        for q in state.canonical.active_quests
        if q.status != "not_started"
    ]
    # Fall back to all quests if none are active yet, so the lore agent still
    # has some quest context on turn 1.
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
    """Package everything the NPC Agent needs to respond as a specific NPC."""
    npc_state = state.canonical.npc_states.get(npc_id)
    if npc_state is None:
        raise ValueError(f"No NPC with id '{npc_id}' in current state.")

    # Pull authoring-time detail (personality, role, knowledge) from seed JSON
    # since the runtime NPCState model does not carry these fields yet.
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
        # `knowledge` from the seed is used as starting memory.
        # Later, this list can grow as the NPC accumulates real interaction memory.
        relevant_memory=npc_seed.get("knowledge", []),
    )


def build_quest_agent_input(state: GameState) -> QuestAgentInput:
    """Package everything the Quest Agent needs to reason about progression."""
    # Active quest summaries from live state so status is always current.
    active_quest_summaries = [
        f"{q.name}: {q.status}" for q in state.canonical.active_quests
    ]

    # Completed objectives across all active quests.
    completed_objectives = [
        obj.description
        for q in state.canonical.active_quests
        for obj in q.objectives
        if obj.completed
    ]

    # Recent player choices — pulled from recent events for now. When memory
    # tracking gets richer, this can become its own dedicated field.
    recent_player_choices = [
        e.summary
        for e in state.canonical.recent_events[-5:]
        if e.event_type in ("player_choice", "branch_taken")
    ]

    # Lightweight cross-agent context: the current scene description doubles
    # as world context, and a list of on-scene NPCs as NPC context.
    location_key = state.canonical.location
    npcs_here = get_npcs_at_location(state, location_key)
    npc_names = [
        state.canonical.npc_states[nid].name
        for nid in npcs_here
        if nid in state.canonical.npc_states
    ]
    npc_context = (
        f"NPCs present: {', '.join(npc_names)}" if npc_names else None
    )

    return QuestAgentInput(
        player_action=state.turn.player_action,
        current_scene=state.canonical.current_scene,
        active_quest_summaries=active_quest_summaries,
        completed_objectives=completed_objectives,
        recent_player_choices=recent_player_choices,
        world_context=state.canonical.current_scene,
        npc_context=npc_context,
    )