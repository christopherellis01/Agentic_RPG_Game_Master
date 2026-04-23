from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


# Input schema: what the orchestrator must provide for the Quest Agent to reason about progression.
# Mirrors the "Input received" section for the Quest Agent in architecture.md:
# active quest data, completed events, relevant player choices, and surrounding world/NPC context.
class QuestAgentInput(BaseModel):
    player_action: str
    current_scene: str
    # Active quests the player is currently working on. Kept as a list of short
    # summaries rather than full quest objects so prompts stay compact.
    active_quest_summaries: List[str] = Field(default_factory=list)
    # Objectives already marked complete in canonical state. Used so the agent
    # does not propose re-completing something or contradict prior progress.
    completed_objectives: List[str] = Field(default_factory=list)
    # Recent player choices that may have branched or altered a quest.
    recent_player_choices: List[str] = Field(default_factory=list)
    # Lightweight context from the world and NPC layers so the quest agent
    # can stay consistent with lore and active characters.
    world_context: Optional[str] = None
    npc_context: Optional[str] = None


# Output schema: structured proposal for how this turn affects quest state.
# The agent NEVER commits changes — these are proposals for the Critic / State Updater.
class QuestAgentOutput(BaseModel):
    # Plain-language interpretation of whether the player advanced, stalled,
    # failed, or altered a quest on this turn.
    progress_interpretation: str
    # Objective-level status markers, e.g. "objective_find_map: completed"
    # or "objective_rescue_brother: in_progress". Kept as strings to stay
    # simple for the first prototype; can be tightened to a typed model later.
    objective_status_updates: List[str] = Field(default_factory=list)
    # New quest hooks, side branches, or optional threads the action opened up.
    new_branches_or_hooks: List[str] = Field(default_factory=list)
    # Reward proposals (items, xp, reputation, etc.). Still proposals — not committed.
    proposed_rewards: List[str] = Field(default_factory=list)
    # Next logical step to surface to the player or to the orchestrator.
    suggested_next_step: Optional[str] = None


# System prompt intentionally mirrors the tone of the lore and NPC agents:
# bounded role, "do not modify state directly", "return structured output".
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
    # Prompt format matches the style used by run_lore_agent and run_npc_agent:
    # labeled sections, bulleted lists for list fields, and an Instructions block at the end.
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