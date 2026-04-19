from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


class LoreAgentInput(BaseModel):
    player_action: str
    current_scene: str
    location: str
    world_summary: str
    relevant_facts: List[str] = Field(default_factory=list)
    active_quest_summaries: List[str] = Field(default_factory=list)


class LoreAgentOutput(BaseModel):
    summary: str
    environmental_details: List[str] = Field(default_factory=list)
    lore_facts_used: List[str] = Field(default_factory=list)
    proposed_consequences: List[str] = Field(default_factory=list)
    suggested_next_step: Optional[str] = None


lore_agent = Agent(
    model=get_model("claude-sonnet-4-6"),
    output_type=LoreAgentOutput,
    system_prompt=(
        "You are the Lore Agent for a lightweight tabletop RPG system. "
        "Your job is to provide grounded world knowledge, environmental context, "
        "and lore-consistent consequences. Stay tightly anchored to the provided "
        "context. Do not invent major canon changes. Do not modify state directly. "
        "Return structured output that helps the orchestrator and downstream nodes."
    ),
)


async def run_lore_agent(agent_input: LoreAgentInput) -> LoreAgentOutput:
    prompt = f"""
Player action:
{agent_input.player_action}

Current scene:
{agent_input.current_scene}

Current location:
{agent_input.location}

World summary:
{agent_input.world_summary}

Relevant facts:
{chr(10).join(f"- {fact}" for fact in agent_input.relevant_facts) if agent_input.relevant_facts else "- None provided"}

Active quest summaries:
{chr(10).join(f"- {q}" for q in agent_input.active_quest_summaries) if agent_input.active_quest_summaries else "- None provided"}

Instructions:
- Explain what the player would notice, learn, or understand from the world context.
- Keep the response grounded in the provided setting.
- Include possible lore-safe consequences if the action would change the situation.
- Do not narrate final player-facing prose like a full game master response.
- Do not commit state changes.
"""
    result = await lore_agent.run(prompt)
    return result.output