"""
FastAPI demo server. Run: uvicorn src.api:app --reload --port 8000
Endpoints: GET /state  POST /turn  POST /reset
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.state_manager import build_initial_state, start_new_turn
from src.router import classify_route
from src.retrieval import (
    build_lore_agent_input,
    build_npc_agent_input,
    build_quest_agent_input,
    get_location_data,
    get_npc_data,
)
from src.agents.lore_agent import LoreAgentInput, LoreAgentOutput, run_lore_agent
from src.agents.npc_agent import NPCAgentInput, NPCAgentOutput, run_npc_agent
from src.agents.quest_agent import QuestAgentInput, QuestAgentOutput, run_quest_agent
from src.agents.critic_agent import (
    CriticInput,
    CriticOutput,
    run_critic_agent,
    fallback_critic_output,
)
from src.models.state_models import GameState, EventRecord
from src.agents.rules_agent import RulesAgentInput, run_rules_agent
from src.state_updater import StatePatch, apply_state_patches

app = FastAPI(title="Agentic RPG Game Master — Demo API")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = PROJECT_ROOT / "demo"

app.mount("/demo", StaticFiles(directory=DEMO_DIR), name="demo")


@app.middleware("http")
async def add_demo_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in {"/", "/demo/shattered_vale_demo.html"}:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_workspace_probe():
    return JSONResponse({})


@app.get("/")
def read_root():
    return FileResponse(
        DEMO_DIR / "shattered_vale_demo.html",
        headers={"Cache-Control": "no-store"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_state: Optional[GameState] = None
# Browser frontend hard-aborts at 30 s; leave a small buffer.
AGENT_TIMEOUT_SECONDS = 25


def _get_state() -> GameState:
    global _state
    if _state is None:
        _state = build_initial_state(
            session_id="live_demo",
            player_action="The player enters the world.",
        )
    return _state


class AgentRunRecord(BaseModel):
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
    critic: Optional[Dict[str, Any]] = None


class StateSnapshot(BaseModel):
    location: str
    scene: str
    npcs: List[Dict[str, Any]]
    quests: List[Dict[str, Any]]
    combatants: List[Dict[str, Any]] = Field(default_factory=list)


class TurnRequest(BaseModel):
    player_action: str
    target_npc_id: Optional[str] = None


def _public_snapshot(state: GameState) -> Dict[str, Any]:
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


async def _run_agent_with_fallback(coro, fallback):
    try:
        return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_SECONDS), False
    except Exception:
        return fallback, True


def _fallback_npc_output(agent_input: NPCAgentInput) -> NPCAgentOutput:
    name = agent_input.npc_name
    name_key = name.lower()
    memory = agent_input.relevant_memory[0] if agent_input.relevant_memory else ""
    goal = agent_input.npc_goals[0] if agent_input.npc_goals else "keep control of the situation"
    traits = ", ".join(agent_input.npc_personality[:3]) or "careful"

    if "mara" in name_key:
        speech = (
            "Mara keeps wiping the same clean cup, eyes moving from you to the room "
            "and back again. \"If you are looking for trouble, you will find it fast "
            "enough. If you are looking to help, then listen before you swing a blade.\""
        )
        if memory:
            speech += f"\n\n\"{memory}\""
        speech += "\n\n\"Oakshade does not need another brave fool. It needs someone who can keep their head.\""
        intent = "Test whether the player is useful without alarming the inn."
        consequence = "Mara becomes slightly more willing to share village rumors."
        next_step = "Ask Mara about the missing scout, Corvin, or the Village Council."
    elif "corvin" in name_key:
        speech = (
            "Corvin does not answer right away. He tilts his hood just enough to study "
            "the exits, then slides his voice low. \"Names carry farther than coin in "
            "this village. Speak softly if you want the truth.\""
        )
        if memory:
            speech += f"\n\n\"{memory}\""
        speech += "\n\n\"If you can move without drawing the Council's eye, I may have work worth your risk.\""
        intent = "Measure whether the player can be recruited for discreet investigation."
        consequence = "Corvin marks the player as a possible covert ally."
        next_step = "Ask Corvin about the map, the Ashen Band, or meeting away from Mara."
    elif "harlan" in name_key:
        speech = (
            "Harlan's hammer pauses above the anvil. \"Hearing? I hear plenty. Most of "
            "it is bad for business, and worse for anyone with a family to feed.\""
        )
        if memory:
            speech += f"\n\nHe looks toward the stacked scrap metal. \"{memory}\""
        speech += "\n\n\"You press me gentle, I might talk. You press me hard, I forget everything.\""
        intent = "Deflect blame while deciding whether the player is a threat or customer."
        consequence = "Harlan stays nervous but can be persuaded with a careful approach."
        next_step = "Ask Harlan about the strange metal or offer to buy gear before pressing him."
    else:
        speech = (
            f"{name} answers in a {traits} way, weighing your words against their need to "
            f"{goal}. "
        )
        if memory:
            speech += f"\"{memory}\""
        else:
            speech += "\"There is more going on here than people are saying aloud.\""
        intent = f"Respond according to their role while trying to {goal}."
        consequence = f"{name} remains engaged, but their trust is not guaranteed."
        next_step = "Ask a more specific question or follow the lead they offered."

    return NPCAgentOutput(
        speech=speech,
        emotional_tone=f"LOCAL FALLBACK · {agent_input.npc_disposition.upper()}",
        intent=intent,
        proposed_social_consequences=[consequence],
        suggested_next_step=next_step,
    )


def _fallback_lore_output(agent_input: LoreAgentInput) -> LoreAgentOutput:
    facts = agent_input.relevant_facts[:2]
    fact_text = " ".join(facts) if facts else agent_input.world_summary
    summary = (
        f"You take in {agent_input.location}. {agent_input.current_scene}"
    )
    if fact_text:
        summary += f"\n\nWhat stands out: {fact_text}"

    return LoreAgentOutput(
        summary=summary,
        environmental_details=facts,
        lore_facts_used=facts,
        proposed_consequences=[
            "The scene remains stable while the player gathers context."
        ],
        suggested_next_step="Choose a person to question or a place to inspect more closely.",
    )


def _fallback_quest_output(agent_input: QuestAgentInput) -> QuestAgentOutput:
    quest_summary = (
        agent_input.active_quest_summaries[0]
        if agent_input.active_quest_summaries
        else "No active quest is clearly advanced."
    )
    return QuestAgentOutput(
        progress_interpretation=(
            f"The action is relevant to the current situation, but no objective is "
            f"completed automatically. Current quest context: {quest_summary}"
        ),
        objective_status_updates=[],
        new_branches_or_hooks=[
            "The player has signaled willingness to investigate the local trouble."
        ],
        proposed_rewards=[],
        suggested_next_step="Follow up with an NPC or travel toward the suspicious lead.",
    )


def _build_critic_input(
    state: GameState,
    route: str,
    player_action: str,
    target_npc_id: Optional[str],
    npc_payload: Optional[Dict[str, Any]],
    npc_known_facts: List[str],
    npc_disposition: str,
    npc_name: str,
    lore_payload: Optional[Dict[str, Any]],
    world_facts: List[str],
    quest_payload: Optional[Dict[str, Any]],
    rules_payload: Optional[Dict[str, Any]],
) -> CriticInput:
    """Package all specialist proposals and state context for the critic."""
    npc_states_snap = {
        nid: {
            "name": n.name,
            "location": n.location,
            "disposition": n.disposition,
        }
        for nid, n in state.canonical.npc_states.items()
    }

    quest_states_snap = [
        {
            "quest_id": q.quest_id,
            "name": q.name,
            "status": q.status,
            "objectives": [
                {
                    "objective_id": o.objective_id,
                    "description": o.description,
                    "completed": o.completed,
                }
                for o in q.objectives
            ],
        }
        for q in state.canonical.active_quests
    ]

    combatant_states_snap = {
        cid: {
            "name": c.name,
            "hp": c.hp,
            "max_hp": c.max_hp,
            "is_hostile": c.is_hostile,
        }
        for cid, c in state.canonical.combatants.items()
    }

    return CriticInput(
        player_action=player_action,
        route=route,
        current_location=state.canonical.location,
        current_scene=state.canonical.current_scene,
        npc_states=npc_states_snap,
        quest_states=quest_states_snap,
        combatant_states=combatant_states_snap,
        npc_proposal=npc_payload,
        npc_known_facts=npc_known_facts,
        npc_disposition=npc_disposition,
        npc_name=npc_name,
        lore_proposal=lore_payload,
        world_facts=world_facts,
        quest_proposal=quest_payload,
        rules_proposal=rules_payload,
    )


@app.get("/state", response_model=StateSnapshot)
def get_state() -> Dict[str, Any]:
    return _public_snapshot(_get_state())


@app.post("/reset", response_model=StateSnapshot)
def reset_state() -> Dict[str, Any]:
    global _state
    _state = build_initial_state(
        session_id="live_demo",
        player_action="The player enters the world.",
    )
    return _public_snapshot(_state)


@app.post("/turn", response_model=TurnResponse)
async def run_turn(req: TurnRequest) -> Dict[str, Any]:
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
    critic_payload: Optional[Dict[str, Any]] = None

    # Context gathered for the critic
    npc_known_facts: List[str] = []
    npc_disposition: str = "neutral"
    npc_name: str = ""
    world_facts: List[str] = []

    # State patches deferred until after critic validates
    pending_patches: List[StatePatch] = []

    goblin = state.canonical.combatants.get("goblin")

    want_npc = bool(req.target_npc_id) or decision.route in ("dialogue", "mixed_action")
    want_lore = decision.route in ("lore_query", "exploration")
    want_quest = decision.route in ("quest_progression", "mixed_action")
    want_rules = decision.route in ("combat", "mixed_action")

    if want_npc and req.target_npc_id:
        npc_input = build_npc_agent_input(state, npc_id=req.target_npc_id)

        # Gather NPC context for the critic
        npc_seed = get_npc_data(req.target_npc_id) or {}
        npc_known_facts = npc_input.relevant_memory
        npc_disposition = npc_input.npc_disposition
        npc_name = npc_input.npc_name

        npc_output, used_fallback = await _run_agent_with_fallback(
            run_npc_agent(npc_input),
            _fallback_npc_output(npc_input),
        )
        npc_payload = npc_output.model_dump()
        npc_state = state.canonical.npc_states.get(req.target_npc_id)
        dialogue.append({
            "who": req.target_npc_id.split("_")[0],
            "speaker": npc_state.name if npc_state else req.target_npc_id,
            "tone": npc_output.emotional_tone,
            "said": npc_output.speech,
        })
        activity.append({
            "name": "npc",
            "status": "done",
            "summary": (
                f"Voiced {npc_state.name if npc_state else req.target_npc_id}"
                f"{' (local fallback)' if used_fallback else ''}."
            ),
        })
    elif want_npc:
        activity.append({
            "name": "npc",
            "status": "skipped",
            "summary": "No NPC target provided for dialogue action.",
        })

    if want_lore:
        lore_input = build_lore_agent_input(state)

        # Gather location facts for the critic
        location_data = get_location_data(state.canonical.location) or {}
        world_facts = location_data.get("relevant_facts", [])

        lore_output, used_fallback = await _run_agent_with_fallback(
            run_lore_agent(lore_input),
            _fallback_lore_output(lore_input),
        )
        lore_payload = lore_output.model_dump()
        dialogue.append({
            "who": "narrator",
            "speaker": "Narrator",
            "tone": (
                "LOCAL FALLBACK · ENVIRONMENTAL DETAIL"
                if used_fallback
                else "LORE-GROUNDED · ENVIRONMENTAL DETAIL"
            ),
            "said": lore_output.summary,
        })
        activity.append({
            "name": "lore",
            "status": "done",
            "summary": (
                "Grounded response in seeded world facts"
                f"{' (local fallback)' if used_fallback else ''}."
            ),
        })

    if want_quest:
        quest_input = build_quest_agent_input(state)
        quest_output, used_fallback = await _run_agent_with_fallback(
            run_quest_agent(quest_input),
            _fallback_quest_output(quest_input),
        )
        quest_payload = quest_output.model_dump()
        activity.append({
            "name": "quest",
            "status": "done",
            "summary": (
                quest_output.progress_interpretation[:120]
                + (" (local fallback)" if used_fallback else "")
            ),
        })

        state.canonical.recent_events.append(EventRecord(
            event_type="quest_interpretation",
            summary=quest_output.progress_interpretation[:200],
            source_node="quest_agent",
        ))

    if want_rules:
        if goblin and goblin.hp <= 0:
            rules_payload = {
                "resolution_type": "combat",
                "outcome": "already_resolved",
                "mechanical_summary": "The Goblin is already defeated.",
                "damage_dealt": 0,
                "damage_taken": 0,
                "status_effects": [],
                "proposed_state_changes": [],
                "suggested_next_step": "Choose a different action.",
            }
            activity.append({
                "name": "rules",
                "status": "done",
                "summary": "The Goblin is already defeated.",
            })
            dialogue.append({
                "who": "narrator",
                "speaker": "Rules Agent",
                "tone": "RULES · RESOLUTION",
                "said": "The Goblin is already defeated.",
            })
        else:
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

            # Collect the state patch — do NOT apply yet
            if goblin and rules_output.damage_dealt > 0:
                new_goblin_hp = max(goblin.hp - rules_output.damage_dealt, 0)
                pending_patches.append(StatePatch(
                    target_type="combatant",
                    target_id="goblin",
                    field="hp",
                    operation="set",
                    value=new_goblin_hp,
                    reason=rules_output.mechanical_summary,
                    source_node="rules_agent",
                ))

            dialogue.append({
                "who": "narrator",
                "speaker": "Rules Agent",
                "tone": "RULES · RESOLUTION",
                "said": rules_output.mechanical_summary,
            })

    critic_input = _build_critic_input(
        state=state,
        route=decision.route,
        player_action=req.player_action,
        target_npc_id=req.target_npc_id,
        npc_payload=npc_payload,
        npc_known_facts=npc_known_facts,
        npc_disposition=npc_disposition,
        npc_name=npc_name,
        lore_payload=lore_payload,
        world_facts=world_facts,
        quest_payload=quest_payload,
        rules_payload=rules_payload,
    )

    critic_output, critic_used_fallback = await _run_agent_with_fallback(
        run_critic_agent(critic_input),
        fallback_critic_output(),
    )
    critic_payload = critic_output.model_dump()

    verdict_label = critic_output.verdict.upper()
    critic_summary = critic_output.summary[:140]
    if critic_output.issues:
        issue_count = len(critic_output.issues)
        critic_summary = f"{verdict_label} ({issue_count} issue{'s' if issue_count != 1 else ''}) — {critic_summary}"
    else:
        critic_summary = f"{verdict_label} — {critic_summary}"

    if critic_used_fallback:
        critic_summary += " (critic unavailable)"

    activity.append({
        "name": "critic",
        "status": "done",
        "summary": critic_summary,
    })

    # Surface critic rejections to the dialogue
    if critic_output.verdict == "reject" and critic_output.issues:
        error_issues = [i for i in critic_output.issues if i.severity == "error"]
        if error_issues:
            dialogue.append({
                "who": "narrator",
                "speaker": "Critic",
                "tone": "CRITIC · REJECTED",
                "said": (
                    f"The critic blocked this proposal: {error_issues[0].description} "
                    f"Suggested correction: {critic_output.suggested_corrections[0] if critic_output.suggested_corrections else 'Review the specialist output.'}"
                ),
            })

    if pending_patches and critic_output.verdict != "reject":
        state_update_result = apply_state_patches(
            state=state,
            patches=pending_patches,
            source_node="state_updater",
        )
        activity.append({
            "name": "state",
            "status": "done",
            "summary": "; ".join(state_update_result.messages),
        })
    elif pending_patches and critic_output.verdict == "reject":
        activity.append({
            "name": "state",
            "status": "skipped",
            "summary": f"State patches blocked by critic: {critic_output.summary[:100]}",
        })
    else:
        activity.append({
            "name": "state",
            "status": "skipped",
            "summary": "No state patches needed this turn.",
        })

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
            "summary": "Narrator not needed for this route.",
        })

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
        "critic": critic_payload,
    }
