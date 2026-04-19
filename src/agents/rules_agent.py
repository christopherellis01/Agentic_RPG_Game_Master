from __future__ import annotations

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
    damage_dealt: int = 0
    damage_taken: int = 0
    status_effects: List[str] = Field(default_factory=list)
    proposed_state_changes: List[str] = Field(default_factory=list)
    suggested_next_step: Optional[str] = None


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