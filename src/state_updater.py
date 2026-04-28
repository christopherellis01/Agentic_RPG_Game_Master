from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.models.state_models import EventRecord, GameState


PatchOperation = Literal["set", "increment", "decrement", "append", "remove"]
PatchTargetType = Literal[
    "combatant",
    "party",
    "inventory",
    "quest",
    "npc",
    "scene",
    "location",
    "metadata",
]


class StatePatch(BaseModel):
    target_type: PatchTargetType
    target_id: Optional[str] = None
    field: str
    operation: PatchOperation
    value: Any
    reason: str
    source_node: str = "unknown"


class StateUpdateResult(BaseModel):
    applied_count: int = 0
    skipped_count: int = 0
    applied_patches: List[StatePatch] = Field(default_factory=list)
    skipped_patches: List[StatePatch] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)


def apply_state_patches(
    state: GameState,
    patches: List[StatePatch],
    *,
    source_node: str = "state_updater",
) -> StateUpdateResult:
    result = StateUpdateResult()

    for patch in patches:
        applied, message = _apply_single_patch(state, patch)

        if applied:
            result.applied_count += 1
            result.applied_patches.append(patch)
            result.messages.append(message)
            _log_state_event(state, "state_patch_applied", message, source_node)
        else:
            result.skipped_count += 1
            result.skipped_patches.append(patch)
            result.messages.append(message)
            _log_state_event(state, "state_patch_skipped", message, source_node)

    return result


def _apply_single_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if patch.target_type == "combatant":
        return _apply_combatant_patch(state, patch)
    if patch.target_type == "party":
        return _apply_party_patch(state, patch)
    if patch.target_type == "inventory":
        return _apply_inventory_patch(state, patch)
    if patch.target_type == "scene":
        return _apply_scene_patch(state, patch)
    if patch.target_type == "location":
        return _apply_location_patch(state, patch)
    if patch.target_type == "npc":
        return _apply_npc_patch(state, patch)
    if patch.target_type == "quest":
        return _apply_quest_patch(state, patch)
    if patch.target_type == "metadata":
        return _apply_metadata_patch(state, patch)
    return False, f"Unsupported patch target_type: {patch.target_type}"


def _apply_combatant_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not patch.target_id:
        return False, "Combatant patch skipped: missing target_id."
    if not hasattr(state.canonical, "combatants"):
        return False, "Combatant patch skipped: state.canonical.combatants does not exist yet."

    combatants = state.canonical.combatants
    if patch.target_id not in combatants:
        return False, f"Combatant patch skipped: combatant '{patch.target_id}' was not found."

    combatant = combatants[patch.target_id]
    if not hasattr(combatant, patch.field):
        return False, f"Combatant patch skipped: combatant '{patch.target_id}' has no field '{patch.field}'."

    old_value = getattr(combatant, patch.field)
    new_value = _calculate_new_value(old_value, patch)

    if patch.field == "hp":
        new_value = _clamp_hp(new_value, max_hp=getattr(combatant, "max_hp", None))

    setattr(combatant, patch.field, new_value)
    return True, (
        f"Updated combatant '{patch.target_id}' field '{patch.field}' "
        f"from {old_value} to {new_value}. Reason: {patch.reason}"
    )


def _apply_party_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not hasattr(state.canonical, "party_status"):
        return False, "Party patch skipped: state.canonical.party_status does not exist."

    party_status = state.canonical.party_status
    if not hasattr(party_status, patch.field):
        return False, f"Party patch skipped: party_status has no field '{patch.field}'."

    old_value = getattr(party_status, patch.field)
    new_value = _calculate_new_value(old_value, patch)

    if patch.field == "hp":
        new_value = _clamp_hp(new_value, max_hp=getattr(party_status, "max_hp", None))

    setattr(party_status, patch.field, new_value)
    return True, (
        f"Updated party field '{patch.field}' from {old_value} to {new_value}. "
        f"Reason: {patch.reason}"
    )


def _apply_inventory_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not hasattr(state.canonical, "inventory"):
        return False, "Inventory patch skipped: state.canonical.inventory does not exist."

    inventory = state.canonical.inventory

    if patch.operation == "append":
        if patch.value not in inventory:
            inventory.append(patch.value)
            return True, f"Added '{patch.value}' to inventory. Reason: {patch.reason}"
        return False, f"Inventory already contains '{patch.value}'."

    if patch.operation == "remove":
        if patch.value in inventory:
            inventory.remove(patch.value)
            return True, f"Removed '{patch.value}' from inventory. Reason: {patch.reason}"
        return False, f"Inventory does not contain '{patch.value}'."

    return False, f"Inventory patch skipped: unsupported operation '{patch.operation}'."


def _apply_scene_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if patch.field != "current_scene":
        return False, "Scene patch skipped: field must be 'current_scene'."
    old_value = state.canonical.current_scene
    state.canonical.current_scene = str(patch.value)
    return True, f"Updated current scene from '{old_value}' to '{patch.value}'. Reason: {patch.reason}"


def _apply_location_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if patch.field != "location":
        return False, "Location patch skipped: field must be 'location'."
    old_value = state.canonical.location
    state.canonical.location = str(patch.value)
    return True, f"Updated location from '{old_value}' to '{patch.value}'. Reason: {patch.reason}"


def _apply_npc_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not patch.target_id:
        return False, "NPC patch skipped: missing target_id."
    if not hasattr(state.canonical, "npc_states"):
        return False, "NPC patch skipped: state.canonical.npc_states does not exist."

    npc_states = state.canonical.npc_states
    if patch.target_id not in npc_states:
        return False, f"NPC patch skipped: npc '{patch.target_id}' was not found."

    npc = npc_states[patch.target_id]
    if not hasattr(npc, patch.field):
        return False, f"NPC patch skipped: npc '{patch.target_id}' has no field '{patch.field}'."

    old_value = getattr(npc, patch.field)
    new_value = _calculate_new_value(old_value, patch)
    setattr(npc, patch.field, new_value)
    return True, (
        f"Updated NPC '{patch.target_id}' field '{patch.field}' "
        f"from {old_value} to {new_value}. Reason: {patch.reason}"
    )


def _apply_quest_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not patch.target_id:
        return False, "Quest patch skipped: missing target_id."
    if not hasattr(state.canonical, "active_quests"):
        return False, "Quest patch skipped: state.canonical.active_quests does not exist."

    quest = next((q for q in state.canonical.active_quests if q.quest_id == patch.target_id), None)
    if quest is None:
        return False, f"Quest patch skipped: quest '{patch.target_id}' was not found."

    if patch.field == "status":
        old_value = quest.status
        quest.status = str(patch.value)
        return True, (
            f"Updated quest '{patch.target_id}' status from {old_value} to {quest.status}. "
            f"Reason: {patch.reason}"
        )

    if patch.field == "objective_completed":
        objective_id = str(patch.value)
        for objective in quest.objectives:
            if objective.objective_id == objective_id:
                old_value = objective.completed
                objective.completed = True
                return True, (
                    f"Marked objective '{objective_id}' complete for quest '{patch.target_id}' "
                    f"from {old_value} to True. Reason: {patch.reason}"
                )
        return False, f"Quest patch skipped: objective '{objective_id}' was not found for quest '{patch.target_id}'."

    return False, f"Quest patch skipped: unsupported field '{patch.field}'."


def _apply_metadata_patch(state: GameState, patch: StatePatch) -> tuple[bool, str]:
    if not hasattr(state.canonical, patch.field):
        return False, f"Metadata patch skipped: canonical state has no field '{patch.field}'."

    old_value = getattr(state.canonical, patch.field)
    new_value = _calculate_new_value(old_value, patch)
    setattr(state.canonical, patch.field, new_value)
    return True, (
        f"Updated canonical field '{patch.field}' from {old_value} to {new_value}. "
        f"Reason: {patch.reason}"
    )


def _calculate_new_value(old_value: Any, patch: StatePatch) -> Any:
    if patch.operation == "set":
        return patch.value
    if patch.operation == "increment":
        return old_value + patch.value
    if patch.operation == "decrement":
        return old_value - patch.value
    if patch.operation == "append":
        if not isinstance(old_value, list):
            raise TypeError("append operation requires an existing list value.")
        new_list = list(old_value)
        new_list.append(patch.value)
        return new_list
    if patch.operation == "remove":
        if not isinstance(old_value, list):
            raise TypeError("remove operation requires an existing list value.")
        new_list = list(old_value)
        if patch.value in new_list:
            new_list.remove(patch.value)
        return new_list
    raise ValueError(f"Unsupported patch operation: {patch.operation}")


def _clamp_hp(value: Any, max_hp: Optional[int] = None) -> int:
    hp = max(int(value), 0)
    if max_hp is not None:
        hp = min(hp, int(max_hp))
    return hp


def _log_state_event(state: GameState, event_type: str, summary: str, source_node: str) -> None:
    event = EventRecord(event_type=event_type, summary=summary, source_node=source_node)
    if hasattr(state.canonical, "recent_events"):
        state.canonical.recent_events.append(event)
    if hasattr(state.turn, "current_turn_events"):
        state.turn.current_turn_events.append(event)


def build_combatant_hp_patch(
    *,
    combatant_id: str,
    new_hp: int,
    reason: str,
    source_node: str = "rules_agent",
) -> StatePatch:
    return StatePatch(
        target_type="combatant",
        target_id=combatant_id,
        field="hp",
        operation="set",
        value=new_hp,
        reason=reason,
        source_node=source_node,
    )


def build_party_hp_patch(
    *,
    new_hp: int,
    reason: str,
    source_node: str = "rules_agent",
) -> StatePatch:
    return StatePatch(
        target_type="party",
        target_id="party",
        field="hp",
        operation="set",
        value=new_hp,
        reason=reason,
        source_node=source_node,
    )
