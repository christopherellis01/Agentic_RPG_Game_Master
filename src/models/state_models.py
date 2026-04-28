from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class EventRecord(BaseModel):
    event_type: str
    summary: str
    source_node: Optional[str] = None


class NPCState(BaseModel):
    npc_id: str
    name: str
    location: str
    disposition: Literal["friendly", "neutral", "hostile"] = "neutral"
    last_interaction_summary: Optional[str] = None
    known_facts: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)


class QuestObjective(BaseModel):
    objective_id: str
    description: str
    completed: bool = False


class QuestState(BaseModel):
    quest_id: str
    name: str
    status: Literal["not_started", "active", "completed", "failed"] = "not_started"
    objectives: List[QuestObjective] = Field(default_factory=list)
    quest_giver_id: Optional[str] = None


class PartyStatus(BaseModel):
    hp: int = 20
    max_hp: int = 20
    conditions: List[str] = Field(default_factory=list)
    gold: int = 0


class CombatantState(BaseModel):
    combatant_id: str
    name: str
    hp: int
    max_hp: int
    status_effects: List[str] = Field(default_factory=list)
    is_hostile: bool = True


class SpecialistOutput(BaseModel):
    node_name: str
    summary: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)


class ProposedUpdate(BaseModel):
    update_type: str
    target: str
    changes: Dict[str, Any] = Field(default_factory=dict)
    reason: str


class CanonicalGameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_scene: str
    location: str
    active_quests: List[QuestState] = Field(default_factory=list)
    npc_states: Dict[str, NPCState] = Field(default_factory=dict)
    inventory: List[str] = Field(default_factory=list)
    party_status: PartyStatus = Field(default_factory=PartyStatus)
    recent_events: List[EventRecord] = Field(default_factory=list)
    combatants: Dict[str, CombatantState] = Field(default_factory=dict)


class TransientTurnState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_action: str
    selected_route: Optional[str] = None
    specialist_outputs: List[SpecialistOutput] = Field(default_factory=list)
    proposed_updates: List[ProposedUpdate] = Field(default_factory=list)
    validation_status: Literal["pending", "approved", "rejected"] = "pending"
    current_turn_events: List[EventRecord] = Field(default_factory=list)
    final_response: Optional[str] = None


class SessionExecutionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: int = 1
    session_id: str
    timestamp: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class GameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical: CanonicalGameState
    turn: TransientTurnState
    meta: SessionExecutionMetadata
