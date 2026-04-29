from __future__ import annotations

import random
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


class RulesAgentInput(BaseModel):
    player_action: str
    current_scene: str
    character_hp: int
    character_max_hp: int
    relevant_stats: List[str] = Field(default_factory=list)
    inventory: List[str] = Field(default_factory=list)
    rules_summary: str
    difficulty: str = "medium"
    enemy_name: Optional[str] = None
    enemy_hp: Optional[int] = None


class RulesAgentOutput(BaseModel):
    resolution_type: str
    outcome: str
    mechanical_summary: str
    dice_roll: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0
    status_effects: List[str] = Field(default_factory=list)
    proposed_state_changes: List[str] = Field(default_factory=list)
    suggested_next_step: Optional[str] = None


def resolve_action_deterministic(agent_input: RulesAgentInput) -> Optional[RulesAgentOutput]:
    action = agent_input.player_action.lower().strip()

    if not action:
        return RulesAgentOutput(
            resolution_type="unknown",
            outcome="failure",
            mechanical_summary="No player action was provided.",
            suggested_next_step="Ask the player what they want to do next.",
        )

    if any(keyword in action for keyword in ["attack", "strike", "slash", "shoot", "stab"]):
        enemy_hp = agent_input.enemy_hp if agent_input.enemy_hp is not None else 20
        roll = random.randint(1, 10)

        if roll >= 8:
            damage = random.randint(6, 10)
            outcome = "success"
            summary = f"Clean hit! You roll a {roll} — the attack connects for {damage} damage."
        elif roll >= 5:
            damage = random.randint(2, 5)
            outcome = "partial_success"
            summary = f"Glancing blow. You roll a {roll} — the attack grazes for {damage} damage."
        else:
            damage = 0
            outcome = "failure"
            summary = f"Miss. You roll a {roll} — the attack fails to connect."

        new_enemy_hp = max(enemy_hp - damage, 0)
        proposed_changes = [
            f"{agent_input.enemy_name or 'Enemy'} HP changes from {enemy_hp} to {new_enemy_hp}."
        ]

        return RulesAgentOutput(
            resolution_type="combat",
            outcome=outcome,
            mechanical_summary=summary,
            dice_roll=roll,
            damage_dealt=damage,
            damage_taken=0,
            proposed_state_changes=proposed_changes,
            suggested_next_step="Send this result to the critic/state updater before narration.",
        )

    if any(keyword in action for keyword in ["persuade", "convince", "negotiate", "ask", "talk"]):
        return RulesAgentOutput(
            resolution_type="skill_check",
            outcome="partial_success",
            mechanical_summary=(
                "The social action has a mixed result. The NPC is willing to listen, "
                "but is not fully convinced yet."
            ),
            proposed_state_changes=[
                "NPC attitude shifts slightly toward cautious cooperation."
            ],
            suggested_next_step="The narrator should describe the NPC's guarded response.",
        )

    if any(keyword in action for keyword in ["search", "inspect", "investigate", "look", "examine"]):
        return RulesAgentOutput(
            resolution_type="skill_check",
            outcome="success",
            mechanical_summary=(
                "The exploration action succeeds. The player notices a useful detail "
                "or discovers something relevant in the scene."
            ),
            proposed_state_changes=[
                "Add a discovered clue or useful environmental detail to the scene state."
            ],
            suggested_next_step="The narrator should reveal the discovery in story form.",
        )

    return None


def resolve_action(player_action: str, state: dict) -> dict:
    """Compatibility shim for the standalone rules_agent_module test suite."""
    agent_input = RulesAgentInput(
        player_action=player_action,
        current_scene=state.get("current_scene", "No scene provided."),
        character_hp=state.get("character_hp", 20),
        character_max_hp=state.get("character_max_hp", 20),
        relevant_stats=state.get("relevant_stats", []),
        inventory=state.get("inventory", []),
        rules_summary=state.get(
            "rules_summary",
            "Use simple d10-style resolution for combat, dialogue, and exploration.",
        ),
        difficulty=state.get("difficulty", "medium"),
        enemy_name=state.get("enemy_name"),
        enemy_hp=state.get("enemy_hp"),
    )

    result = resolve_action_deterministic(agent_input)

    if result is None:
        return {
            "action_type": "unknown",
            "outcome": "failure",
            "reason": "Action not recognized by the deterministic rules system.",
            "consequence": {},
        }

    action = player_action.lower().strip()
    consequence = {
        "damage_dealt": result.damage_dealt,
        "damage_taken": result.damage_taken,
        "status_effects": result.status_effects,
        "proposed_state_changes": result.proposed_state_changes,
    }

    if any(keyword in action for keyword in ["persuade", "convince", "negotiate", "ask", "talk"]):
        action_type = "dialogue"
    elif any(keyword in action for keyword in ["search", "inspect", "investigate", "look", "examine"]):
        action_type = "exploration"
    else:
        action_type = result.resolution_type

    if action_type == "combat":
        enemy_hp = state.get("enemy_hp", 20)
        consequence["new_enemy_hp"] = max(enemy_hp - result.damage_dealt, 0)

    return {
        "action_type": action_type,
        "outcome": result.outcome,
        "reason": result.mechanical_summary,
        "consequence": consequence,
    }


rules_agent = Agent(
    model=get_model("claude-sonnet-4-6"),
    output_type=RulesAgentOutput,
    system_prompt=(
        "You are the Rules Agent for a lightweight tabletop RPG system. "
        "Your job is to resolve uncertain actions, combat actions, and skill checks "
        "using the provided simplified rules context. Stay grounded in the rules summary. "
        "Do not invent complex mechanics beyond what is provided. "
        "Do not modify state directly. Return structured output."
    ),
)


async def run_rules_agent(agent_input: RulesAgentInput) -> RulesAgentOutput:
    deterministic_result = resolve_action_deterministic(agent_input)

    if deterministic_result is not None:
        return deterministic_result

    prompt = f"""
Player action:
{agent_input.player_action}

Current scene:
{agent_input.current_scene}

Character HP:
{agent_input.character_hp}/{agent_input.character_max_hp}

Relevant stats:
{", ".join(agent_input.relevant_stats) if agent_input.relevant_stats else "Not provided"}

Inventory:
{", ".join(agent_input.inventory) if agent_input.inventory else "Not provided"}

Rules summary:
{agent_input.rules_summary}

Difficulty:
{agent_input.difficulty}

Enemy name:
{agent_input.enemy_name or "None"}

Enemy HP:
{agent_input.enemy_hp if agent_input.enemy_hp is not None else "None"}

Instructions:
- Decide whether this is a combat action, skill check, contested action, or other rules-based resolution.
- Resolve it using the simplified rules context provided.
- Keep the output practical and structured.
- Suggest state changes, but do not commit them directly.
- Do not narrate the full scene like the narrator agent would.
"""
    result = await rules_agent.run(prompt)
    return result.output
