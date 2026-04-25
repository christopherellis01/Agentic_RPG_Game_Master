"""
FastAPI server that wraps the real agents for the live browser demo.

Endpoints:
  GET  /state        -> current public view of the game state
  POST /turn         -> run one turn with a player action (+ optional NPC target)
  POST /reset        -> rebuild a fresh GameState

Run from the project root:
    uvicorn src.api:app --reload --port 8000

The frontend (demo/shattered_vale_demo.html) calls these endpoints.

Design notes:
  - Only the agents that are real today are called: Lore, NPC, Quest.
  - The router picks the route; we map that route to one specialist call.
  - The frontend passes `target_npc_id` when the action is directed at a specific
    NPC (e.g. "talk to Mara"). This keeps dialogue routing honest without forcing
    the router to guess NPCs from free text.
  - Critic / State Updater / Narrator are not yet implemented in the project,
    so the API reports them as `skipped` rather than pretending they ran.
"""

from __future__ import annotations

from pathlib import Path

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.state_manager import build_initial_state, start_new_turn
from src.router import classify_route
from src.retrieval import (
    build_lore_agent_input,
    build_npc_agent_input,
    build_quest_agent_input,
)
from src.agents.lore_agent import run_lore_agent
from src.agents.npc_agent import run_npc_agent
from src.agents.quest_agent import run_quest_agent
from src.models.state_models import GameState, EventRecord
from src.agents.rules_agent import RulesAgentInput, run_rules_agent
from src.state_updater import StatePatch, apply_state_patches

# APP + CORS
app = FastAPI(title="Agentic RPG Game Master — Demo API")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = PROJECT_ROOT / "demo"

app.mount("/demo", StaticFiles(directory=DEMO_DIR), name="demo")


@app.get("/")
def read_root():
    return FileResponse(DEMO_DIR / "shattered_vale_demo.html")

# Allow the HTML file to talk to the server whether it's opened via file://
# or served from a different port. In production you'd tighten this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# SESSION STATE (single in-memory session for demo purposes)
_state: Optional[GameState] = None


def _get_state() -> GameState:
    global _state
    if _state is None:
        _state = build_initial_state(
            session_id="live_demo",
            player_action="The player enters the world.",
        )
    return _state


# RESPONSE MODELS
class AgentRunRecord(BaseModel):
    """One entry in the agent activity log the UI animates."""
    name: str
    status: str  # "done" | "skipped"
    route: Optional[str] = None
    summary: Optional[str] = None


class TurnResponse(BaseModel):
    route: str
    route_reason: str
    agent_activity: List[AgentRunRecord]
    dialogue: List[Dict[str, Any]] = Field(default_factory=list)
    lore: Optional[Dict[str, Any]] = None
    npc: Optional[Dict[str, Any]] = None
    quest: Optional[Dict[str, Any]] = None
    state_snapshot: Dict[str, Any]
    rules: Optional[Dict[str, Any]] = None


class StateSnapshot(BaseModel):
    location: str
    scene: str
    npcs: List[Dict[str, Any]]
    quests: List[Dict[str, Any]]
    combatants: List[Dict[str, Any]] = Field(default_factory=list)


class TurnRequest(BaseModel):
    player_action: str
    target_npc_id: Optional[str] = None


# HELPERS
def _public_snapshot(state: GameState) -> Dict[str, Any]:
    """Return the parts of state the UI cares about."""
    return {
        "location": state.canonical.location,
        "scene": state.canonical.current_scene,
        "turn_id": state.meta.turn_id,
        "npcs": [
            {
                "id": nid,
                "name": n.name,
                "location": n.location,
                "disposition": n.disposition,
            }
            for nid, n in state.canonical.npc_states.items()
        ],
        "quests": [
            {
                "id": q.quest_id,
                "name": q.name,
                "status": q.status,
                "objectives": [
                    {
                        "id": o.objective_id,
                        "description": o.description,
                        "completed": o.completed,
                    }
                    for o in q.objectives
                ],
            }
            for q in state.canonical.active_quests
        ],
        "combatants": [
            {
                "id": cid,
                "name": c.name,
                "hp": c.hp,
                "max_hp": c.max_hp,
                "status_effects": c.status_effects,
                "is_hostile": c.is_hostile,
            }
            for cid, c in state.canonical.combatants.items()
        ],
    }

# ROUTES
@app.get("/state", response_model=StateSnapshot)
def get_state() -> Dict[str, Any]:
    """Return the public view of the current state (used on page load)."""
    return _public_snapshot(_get_state())


@app.post("/reset", response_model=StateSnapshot)
def reset_state() -> Dict[str, Any]:
    """Rebuild a fresh GameState from seed data."""
    global _state
    _state = build_initial_state(
        session_id="live_demo",
        player_action="The player enters the world.",
    )
    return _public_snapshot(_state)


@app.post("/turn", response_model=TurnResponse)
async def run_turn(req: TurnRequest) -> Dict[str, Any]:
    """
    Execute one turn with the real agents.

    Flow:
      1. Advance turn state with the player's action
      2. Let the router classify the action
      3. Based on the route, call the appropriate real agent(s)
      4. Build a response the UI can render (dialogue + sidebar animation)
    """
    state = _get_state()
    state = start_new_turn(state, req.player_action)

    decision = classify_route(req.player_action, state)
    state.turn.selected_route = decision.route

    activity: List[Dict[str, Any]] = [
        {"name": "router", "status": "done", "route": decision.route, "summary": decision.reason}
    ]

    dialogue: List[Dict[str, Any]] = [
        {"who": "player", "speaker": "You", "tone": None, "said": req.player_action}
    ]

    lore_payload: Optional[Dict[str, Any]] = None
    npc_payload: Optional[Dict[str, Any]] = None
    quest_payload: Optional[Dict[str, Any]] = None
    rules_payload: Optional[Dict[str, Any]] = None

    # Map route -> which real agents fire.
    # If the player targeted an NPC, always run the NPC agent regardless of route,
    # because "talking to Mara" should produce Mara's voice even if the router
    # labels the action as quest_progression.
    want_npc = bool(req.target_npc_id) or decision.route in ("dialogue", "mixed_action")
    want_lore = decision.route in ("lore_query", "exploration")
    want_quest = decision.route in ("quest_progression", "mixed_action")
    want_rules = decision.route in ("combat", "mixed_action")

    try:
        if want_npc and req.target_npc_id:
            npc_input = build_npc_agent_input(state, npc_id=req.target_npc_id)
            npc_output = await run_npc_agent(npc_input)
            npc_payload = npc_output.model_dump()
            npc_state = state.canonical.npc_states.get(req.target_npc_id)
            dialogue.append({
                "who": req.target_npc_id.split("_")[0],  # css class hook
                "speaker": npc_state.name if npc_state else req.target_npc_id,
                "tone": npc_output.emotional_tone,
                "said": npc_output.speech,
            })
            activity.append({
                "name": "npc",
                "status": "done",
                "summary": f"Voiced {npc_state.name if npc_state else req.target_npc_id}.",
            })
        elif want_npc:
            # Dialogue route but no NPC target specified — skip honestly.
            activity.append({
                "name": "npc",
                "status": "skipped",
                "summary": "No NPC target provided for dialogue action.",
            })

        if want_lore:
            lore_input = build_lore_agent_input(state)
            lore_output = await run_lore_agent(lore_input)
            lore_payload = lore_output.model_dump()
            dialogue.append({
                "who": "narrator",
                "speaker": "Narrator",
                "tone": "LORE-GROUNDED · ENVIRONMENTAL DETAIL",
                "said": lore_output.summary,
            })
            activity.append({
                "name": "lore",
                "status": "done",
                "summary": "Grounded response in seeded world facts.",
            })

        if want_quest:
            quest_input = build_quest_agent_input(state)
            quest_output = await run_quest_agent(quest_input)
            quest_payload = quest_output.model_dump()
            activity.append({
                "name": "quest",
                "status": "done",
                "summary": quest_output.progress_interpretation[:140],
            })

            state.canonical.recent_events.append(EventRecord(
                event_type="quest_interpretation",
                summary=quest_output.progress_interpretation[:200],
                source_node="quest_agent",
            ))

        if want_rules:
            goblin = state.canonical.combatants.get("goblin")

            rules_input = RulesAgentInput(
                player_action=req.player_action,
                current_scene=state.canonical.current_scene,
                character_hp=state.canonical.party_status.hp,
                character_max_hp=state.canonical.party_status.max_hp,
                relevant_stats=[],
                inventory=state.canonical.inventory,
                rules_summary=(
                    "Use simple d10-style resolution. High rolls succeed, "
                    "middle rolls partially succeed, low rolls fail. Agents may "
                    "propose state changes but must not commit them directly."
                ),
                difficulty="medium",
                enemy_name=goblin.name if goblin else "Goblin",
                enemy_hp=goblin.hp if goblin else 15,
            )

            rules_output = await run_rules_agent(rules_input)
            rules_payload = rules_output.model_dump()

            activity.append({
                "name": "rules",
                "status": "done",
                "summary": rules_output.mechanical_summary,
            })

        if goblin and rules_output.damage_dealt > 0:
            new_goblin_hp = max(goblin.hp - rules_output.damage_dealt, 0)

            patch = StatePatch(
                target_type="combatant",
                target_id="goblin",
                field="hp",
                operation="set",
                value=new_goblin_hp,
                reason=rules_output.mechanical_summary,
                source_node="rules_agent",
            )

            state_update_result = apply_state_patches(
                state=state,
                patches=[patch],
                source_node="state_updater",
            )

            activity.append({
                "name": "state",
                "status": "done",
                "summary": "; ".join(state_update_result.messages),
            })
        else:
            activity.append({
                "name": "state",
                "status": "skipped",
                "summary": "No combatant HP update was needed.",
            })
            
            dialogue.append({
                "who": "narrator",
                "speaker": "Rules Agent",
                "tone": "RULES · RESOLUTION",
                "said": rules_output.mechanical_summary,
            })
           

    except Exception as e:
        # Don't crash the whole turn if one agent errors — report it honestly.
        activity.append({
            "name": "error",
            "status": "skipped",
            "summary": f"Agent error: {type(e).__name__}: {e}",
        })
        raise HTTPException(status_code=500, detail=str(e))
    
    if rules_payload:
        damage = rules_payload.get("damage_dealt", 0)
        outcome = rules_payload.get("outcome", "unknown")

        if outcome == "success" and damage > 0:
            narration = (
                f"You follow through on your action: {req.player_action} "
                f"The strike lands cleanly, dealing {damage} damage."
            )
        elif outcome == "partial_success" and damage > 0:
            narration = (
                f"You attempt: {req.player_action} "
                f"It partially works, dealing {damage} damage."
            )
        elif outcome == "failure":
            narration = (
                f"You attempt: {req.player_action} "
                "but it does not succeed this time."
            )
        else:
            narration = rules_payload.get(
                "mechanical_summary",
                "The action is resolved.",
            )

        dialogue.append({
            "who": "narrator",
            "speaker": "Narrator",
            "tone": "NARRATION",
            "said": narration,
        })

        activity.append({
            "name": "narrator",
            "status": "done",
            "summary": "Created player-facing narration from Rules Agent output.",
        })
    else:
        activity.append({
            "name": "narrator",
            "status": "skipped",
            "summary": "Narrator not needed for this route yet.",
        })


    # Honest disclosures about what the project does not yet have.
    activity.append({"name": "critic", "status": "skipped", "summary": "Critic not yet implemented."})
    # activity.append({"name": "state", "status": "skipped", "summary": "State Updater not yet implemented."})
    # activity.append({"name": "narrator", "status": "skipped", "summary": "Narrator not yet implemented."})

    return {
        "route": decision.route,
        "route_reason": decision.reason,
        "agent_activity": activity,
        "dialogue": dialogue,
        "lore": lore_payload,
        "npc": npc_payload,
        "quest": quest_payload,
        "state_snapshot": _public_snapshot(state),
        "rules": rules_payload,
    }