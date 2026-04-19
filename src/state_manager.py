from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.models.state_models import (
    CanonicalGameState,
    EventRecord,
    GameState,
    NPCState,
    PartyStatus,
    QuestObjective,
    QuestState,
    SessionExecutionMetadata,
    TransientTurnState,
)


# PROJECT PATHS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

WORLD_PATH = PROJECT_ROOT / "data" / "world" / "world_state.json"
NPC_PATH = PROJECT_ROOT / "data" / "npcs" / "npc_data.json"
QUEST_PATH = PROJECT_ROOT / "data" / "quests" / "quest_data.json"


# JSON HELPERS

def load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return it as a dictionary."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# BUILDERS

def build_npc_states(npc_data: Dict[str, Any]) -> dict[str, NPCState]:
    """Convert npc_data.json into NPCState models keyed by npc_id."""
    npc_states: dict[str, NPCState] = {}

    for npc in npc_data.get("npcs", []):
        npc_id = npc["id"]

        npc_states[npc_id] = NPCState(
            npc_id=npc_id,
            name=npc["name"],
            location=npc["location"],
            disposition="neutral",
            last_interaction_summary=None,
            known_facts=[],
            goals=npc.get("goals", []),
        )

    return npc_states


def build_quest_states(quest_data: Dict[str, Any]) -> list[QuestState]:
    """Convert quest_data.json into QuestState models."""
    quest_states: list[QuestState] = []

    for quest in quest_data.get("quests", []):
        objectives = [
            QuestObjective(
                objective_id=obj["id"],
                description=obj["description"],
                completed=obj.get("completed", False),
            )
            for obj in quest.get("objectives", [])
        ]

        quest_states.append(
            QuestState(
                quest_id=quest["id"],
                name=quest["name"],
                status=quest.get("status", "not_started"),
                objectives=objectives,
                quest_giver_id=quest.get("giver"),
            )
        )

    return quest_states


def build_initial_canonical_state(
    world_data: Dict[str, Any],
    npc_data: Dict[str, Any],
    quest_data: Dict[str, Any],
) -> CanonicalGameState:
    """Build the persistent canonical game state."""
    starting_location = world_data.get("starting_location", "unknown_location")

    current_scene = (
        f"The player arrives at {starting_location}, where rumors, danger, "
        f"and opportunity are beginning to converge."
    )

    recent_events = [
        EventRecord(
            event_type="session_start",
            summary=f"Session initialized in {starting_location}.",
            source_node="state_manager",
        )
    ]

    return CanonicalGameState(
        current_scene=current_scene,
        location=starting_location,
        active_quests=build_quest_states(quest_data),
        npc_states=build_npc_states(npc_data),
        inventory=[],
        party_status=PartyStatus(hp=20, max_hp=20, conditions=[], gold=0),
        recent_events=recent_events,
    )


def build_initial_turn_state(
    player_action: str = "The player enters the world."
) -> TransientTurnState:
    """Build a fresh transient turn state."""
    return TransientTurnState(
        player_action=player_action,
        selected_route=None,
        specialist_outputs=[],
        proposed_updates=[],
        validation_status="pending",
        current_turn_events=[],
        final_response=None,
    )


def build_session_metadata(
    session_id: str = "demo_session_001",
    turn_id: int = 1,
    retry_count: int = 0,
    max_retries: int = 3,
) -> SessionExecutionMetadata:
    """Build session / execution metadata."""
    return SessionExecutionMetadata(
        session_id=session_id,
        turn_id=turn_id,
        timestamp=datetime.utcnow().isoformat(),
        retry_count=retry_count,
        max_retries=max_retries,
    )


# PUBLIC FUNCTION

def build_initial_state(
    session_id: str = "demo_session_001",
    player_action: str = "The player enters the world.",
) -> GameState:
    """Load seed data and return a fresh GameState object."""
    world_data = load_json(WORLD_PATH)
    npc_data = load_json(NPC_PATH)
    quest_data = load_json(QUEST_PATH)

    canonical = build_initial_canonical_state(world_data, npc_data, quest_data)
    turn = build_initial_turn_state(player_action=player_action)
    meta = build_session_metadata(session_id=session_id)

    return GameState(
        canonical=canonical,
        turn=turn,
        meta=meta,
    )


# SAVE STATE FUNCTION

def save_state(state: GameState, path: Path | str) -> None:
    """Save the current GameState to disk as JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f, indent=2)

