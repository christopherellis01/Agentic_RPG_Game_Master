from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


class NPCAgentInput(BaseModel):
    player_action: str
    npc_name: str
    npc_role: str
    npc_personality: List[str] = Field(default_factory=list)
    npc_goals: List[str] = Field(default_factory=list)
    npc_disposition: str = "neutral"
    current_scene: str = ""
    relationship_summary: Optional[str] = None
    relevant_memory: List[str] = Field(default_factory=list)


class NPCAgentOutput(BaseModel):
    speech: str
    emotional_tone: str
    intent: str
    proposed_social_consequences: List[str] = Field(default_factory=list)
    suggested_next_step: Optional[str] = None


npc_agent = Agent(
    model=get_model("claude-sonnet-4-6"),
    output_type=NPCAgentOutput,
    system_prompt=(
        "You are the NPC Agent for a lightweight tabletop RPG system. "
        "Your job is to generate believable NPC dialogue, reactions, and intent "
        "based on the provided profile, goals, disposition, and scene context. "
        "Keep the NPC distinct, grounded, and internally consistent. "
        "Do not modify state directly. Return structured output."
    ),
)


async def run_npc_agent(agent_input: NPCAgentInput) -> NPCAgentOutput:
    prompt = f"""
Player action:
{agent_input.player_action}

NPC name:
{agent_input.npc_name}

NPC role:
{agent_input.npc_role}

NPC personality:
{", ".join(agent_input.npc_personality) if agent_input.npc_personality else "Not provided"}

NPC goals:
{", ".join(agent_input.npc_goals) if agent_input.npc_goals else "Not provided"}

NPC disposition:
{agent_input.npc_disposition}

Current scene:
{agent_input.current_scene}

Relationship summary:
{agent_input.relationship_summary or "None provided"}

Relevant memory:
{chr(10).join(f"- {item}" for item in agent_input.relevant_memory) if agent_input.relevant_memory else "- None provided"}

Instructions:
- Write what the NPC would say or how they would respond.
- Keep the NPC's tone and motives consistent with the provided context.
- Include the likely intent behind the response.
- Suggest social consequences if the interaction changes trust, tension, cooperation, or suspicion.
- Do not write a full narrator response for the whole scene.
- Do not commit state changes.
"""
    result = await npc_agent.run(prompt)
    return result.output