from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


class QuestAgentInput(BaseModel):
    player_action: str
    current_scene: str
    active_quest_summaries: List[str] = Field(default_factory=list)
    completed_objectives: List[str] = Field(default_factory=list)
    recent_player_choices: List[str] = Field(default_factory=list)
    world_context: Optional[str] = None
    npc_context: Optional[str] = None


class QuestAgentOutput(BaseModel):
    progress_interpretation: str
    objective_status_updates: List[str] = Field(default_factory=list)
    new_branches_or_hooks: List[str] = Field(default_factory=list)
    proposed_rewards: List[str] = Field(default_factory=list)
    suggested_next_step: Optional[str] = None


quest_agent = Agent(
    model=get_model("claude-sonnet-4-6"),
    output_type=QuestAgentOutput,
    system_prompt=(
        "You are the Quest Agent for a lightweight tabletop RPG system. "
        "Your job is to interpret how the player's action affects active quests, "
        "including progression, branching, delays, failures, and new hooks. "
        "Stay grounded in the active quest summaries, completed objectives, and "
        "recent player choices provided. Do not invent quests that were never seeded. "
        "Do not modify state directly. Return structured output that the Critic and "
        "State Updater can validate and commit."
    ),
)


async def run_quest_agent(agent_input: QuestAgentInput) -> QuestAgentOutput:
    prompt = f"""
Player action:
{agent_input.player_action}

Current scene:
{agent_input.current_scene}

Active quest summaries:
{chr(10).join(f"- {q}" for q in agent_input.active_quest_summaries) if agent_input.active_quest_summaries else "- None provided"}

Completed objectives:
{chr(10).join(f"- {obj}" for obj in agent_input.completed_objectives) if agent_input.completed_objectives else "- None provided"}

Recent player choices:
{chr(10).join(f"- {choice}" for choice in agent_input.recent_player_choices) if agent_input.recent_player_choices else "- None provided"}

World context:
{agent_input.world_context or "None provided"}

NPC context:
{agent_input.npc_context or "None provided"}

Instructions:
- Decide whether the player's action advanced, stalled, failed, or branched any active quest.
- Only reference quests that appear in the active quest summaries.
- Propose objective status updates if clearly warranted by the action.
- Suggest new branches, hooks, or reward proposals if the action opened them up.
- Do not narrate final player-facing prose like a full game master response.
- Do not commit state changes.
"""
    result = await quest_agent.run(prompt)
    return result.output
