"""
Critic Agent — validates every specialist proposal before state is committed.

Checks:
  - NPC knowledge leaks: NPC speech references facts outside their authorized knowledge
  - Lore contradictions: lore summary conflicts with established world facts
  - Illegal transitions: dead enemy still targeted, already-complete objectives re-completed
  - NPC behavioral consistency: disposition vs. proposed emotional tone

Returns approve / warn / reject with a structured issue list and summary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.llm_client import get_model


class CriticIssue(BaseModel):
    issue_type: Literal[
        "knowledge_leak",
        "lore_contradiction",
        "illegal_transition",
        "invalid_combat",
        "npc_behavior_violation",
        "quest_logic_error",
        "other",
    ]
    severity: Literal["error", "warning", "info"]
    description: str
    agent_source: str


class CriticInput(BaseModel):
    player_action: str
    route: str
    current_location: str
    current_scene: str

    # Simplified state snapshots for validation
    npc_states: Dict[str, Any] = Field(default_factory=dict)
    quest_states: List[Dict[str, Any]] = Field(default_factory=list)
    combatant_states: Dict[str, Any] = Field(default_factory=dict)

    # NPC proposal + what the NPC is authorized to know
    npc_proposal: Optional[Dict[str, Any]] = None
    npc_known_facts: List[str] = Field(default_factory=list)
    npc_disposition: str = "neutral"
    npc_name: str = ""

    # Lore proposal + established world facts
    lore_proposal: Optional[Dict[str, Any]] = None
    world_facts: List[str] = Field(default_factory=list)

    # Quest proposal
    quest_proposal: Optional[Dict[str, Any]] = None

    # Rules/combat proposal
    rules_proposal: Optional[Dict[str, Any]] = None


class CriticOutput(BaseModel):
    verdict: Literal["approve", "warn", "reject"]
    issues: List[CriticIssue] = Field(default_factory=list)
    summary: str
    suggested_corrections: List[str] = Field(default_factory=list)


# --- Deterministic checks (always run, no LLM needed) ---

def _run_deterministic_checks(critic_input: CriticInput) -> List[CriticIssue]:
    issues: List[CriticIssue] = []

    # 1. Combat against already-dead enemy
    if critic_input.rules_proposal:
        damage = critic_input.rules_proposal.get("damage_dealt", 0)
        if damage > 0:
            for cid, c in critic_input.combatant_states.items():
                if c.get("hp", 1) <= 0:
                    issues.append(CriticIssue(
                        issue_type="invalid_combat",
                        severity="warning",
                        description=(
                            f"Rules agent proposed {damage} damage to '{c.get('name', cid)}' "
                            f"whose HP is already 0. Enemy is already defeated."
                        ),
                        agent_source="rules_agent",
                    ))

    # 2. Quest objective already complete
    if critic_input.quest_proposal:
        completed_obj_ids: set[str] = set()
        for q in critic_input.quest_states:
            for obj in q.get("objectives", []):
                if obj.get("completed", False):
                    completed_obj_ids.add(obj.get("objective_id", ""))

        for update in critic_input.quest_proposal.get("objective_status_updates", []):
            # Common pattern: "objective_id: completed" or "objective_id: status"
            obj_id = update.split(":")[0].strip()
            if obj_id in completed_obj_ids:
                issues.append(CriticIssue(
                    issue_type="illegal_transition",
                    severity="warning",
                    description=(
                        f"Quest agent proposed updating '{obj_id}' which is "
                        f"already marked complete. No state change needed."
                    ),
                    agent_source="quest_agent",
                ))

    # 3. Basic NPC disposition vs. proposed tone mismatch
    if critic_input.npc_proposal and critic_input.npc_disposition:
        disposition = critic_input.npc_disposition.lower()
        emotional_tone = (critic_input.npc_proposal.get("emotional_tone") or "").lower()
        if "hostile" in disposition and "friendly" in emotional_tone:
            issues.append(CriticIssue(
                issue_type="npc_behavior_violation",
                severity="info",
                description=(
                    f"NPC disposition is '{critic_input.npc_disposition}' but "
                    f"proposed emotional tone is '{emotional_tone}'. "
                    "Verify de-escalation is intentional."
                ),
                agent_source="npc_agent",
            ))

    return issues


def _needs_llm_check(critic_input: CriticInput) -> bool:
    """LLM check is only needed when there are semantic proposals to validate."""
    return critic_input.npc_proposal is not None or critic_input.lore_proposal is not None


# --- Helper formatters for the LLM prompt ---

def _fmt_npc_check(critic_input: CriticInput) -> str:
    if not critic_input.npc_proposal:
        return "NPC proposal: None"
    npc = critic_input.npc_proposal
    known = critic_input.npc_known_facts
    return (
        f"NPC PROPOSAL — {critic_input.npc_name} (disposition: {critic_input.npc_disposition})\n"
        f"  Proposed speech: {npc.get('speech', '')[:400]}\n"
        f"  Emotional tone: {npc.get('emotional_tone', '')}\n"
        f"  Intent: {npc.get('intent', '')}\n"
        f"  Authorized knowledge:\n"
        + "\n".join(f"    - {f}" for f in known) if known else "    (none listed)"
    )


def _fmt_lore_check(critic_input: CriticInput) -> str:
    if not critic_input.lore_proposal:
        return "Lore proposal: None"
    lore = critic_input.lore_proposal
    facts = critic_input.world_facts
    return (
        f"LORE PROPOSAL\n"
        f"  Summary: {lore.get('summary', '')[:400]}\n"
        f"  Lore facts claimed: {lore.get('lore_facts_used', [])}\n"
        f"  Established world facts:\n"
        + "\n".join(f"    - {f}" for f in facts) if facts else "    (none provided)"
    )


def _fmt_quest_check(critic_input: CriticInput) -> str:
    if not critic_input.quest_proposal:
        return "Quest proposal: None"
    q = critic_input.quest_proposal
    return (
        f"QUEST PROPOSAL\n"
        f"  Interpretation: {q.get('progress_interpretation', '')[:300]}\n"
        f"  Objective updates: {q.get('objective_status_updates', [])}\n"
        f"  New hooks: {q.get('new_branches_or_hooks', [])}"
    )


def _fmt_rules_check(critic_input: CriticInput) -> str:
    if not critic_input.rules_proposal:
        return "Rules proposal: None"
    r = critic_input.rules_proposal
    return (
        f"RULES PROPOSAL\n"
        f"  Outcome: {r.get('outcome', '')} | Damage dealt: {r.get('damage_dealt', 0)} "
        f"| Damage taken: {r.get('damage_taken', 0)}\n"
        f"  Mechanical summary: {r.get('mechanical_summary', '')[:200]}\n"
        f"  Proposed state changes: {r.get('proposed_state_changes', [])}"
    )


def _fmt_combatants(critic_input: CriticInput) -> str:
    if not critic_input.combatant_states:
        return "Combatants: None"
    lines = ["Combatants:"]
    for cid, c in critic_input.combatant_states.items():
        lines.append(
            f"  - {c.get('name', cid)}: HP {c.get('hp', '?')}/{c.get('max_hp', '?')}"
            + (" [DEFEATED]" if c.get("hp", 1) <= 0 else "")
        )
    return "\n".join(lines)


# --- LLM Critic Agent ---

_critic_agent = Agent(
    model=get_model("claude-sonnet-4-6"),
    output_type=CriticOutput,
    system_prompt=(
        "You are the Critic Agent for a tabletop RPG game master system. "
        "Your job is to validate proposals from specialist agents (NPC, Lore, Quest, Rules) "
        "before they are committed to canonical game state.\n\n"
        "Focus on detecting:\n"
        "1. NPC knowledge leaks: Does the NPC's speech reference specific facts, events, "
        "   or people NOT in their authorized knowledge list? This breaks immersion.\n"
        "2. Lore contradictions: Does the lore summary directly contradict the established "
        "   world facts? Minor embellishments are fine; factual conflicts are not.\n"
        "3. NPC behavioral inconsistency: Does the response fundamentally violate the NPC's "
        "   stated disposition? Surprising behavior is OK; contradictory behavior is not.\n"
        "4. Quest logic errors: Do proposed objective updates make sense given the player's action?\n\n"
        "Severity guide:\n"
        "  error — Clear, specific violation (e.g., NPC names a person they have no reason to know)\n"
        "  warning — Possible issue worth surfacing (e.g., lore slightly exceeds established facts)\n"
        "  info — Observation only, does not affect validity\n\n"
        "Verdict:\n"
        "  approve — All proposals are consistent and valid\n"
        "  warn — Minor issues exist but proposals can proceed\n"
        "  reject — A serious factual or consistency violation was found (use sparingly)\n\n"
        "Be strict about knowledge leaks, moderate about lore, lenient about behavior."
    ),
)


async def run_critic_agent(critic_input: CriticInput) -> CriticOutput:
    """
    Run the critic agent against all specialist proposals.

    Phase 1: deterministic structural checks (always run, no LLM).
    Phase 2: LLM semantic check (only when NPC or lore proposals exist).
    """
    deterministic_issues = _run_deterministic_checks(critic_input)

    if not _needs_llm_check(critic_input):
        # No semantic proposals — derive verdict from deterministic issues only
        has_error = any(i.severity == "error" for i in deterministic_issues)
        has_warning = any(i.severity == "warning" for i in deterministic_issues)

        if has_error:
            verdict: Literal["approve", "warn", "reject"] = "reject"
            summary = "Rejected due to structural violation."
        elif has_warning:
            verdict = "warn"
            summary = "Proceeding with caution — minor structural issues detected."
        else:
            verdict = "approve"
            summary = "No proposals required semantic validation. Structural checks passed."

        return CriticOutput(
            verdict=verdict,
            issues=deterministic_issues,
            summary=summary,
        )

    # Build the LLM prompt
    prompt = f"""
=== PLAYER ACTION ===
{critic_input.player_action}
Route: {critic_input.route}

=== CURRENT GAME STATE ===
Location: {critic_input.current_location}
Scene: {critic_input.current_scene[:300]}

{_fmt_combatants(critic_input)}

Active quests: {[q.get('quest_id', '?') + ' (' + q.get('status', '?') + ')' for q in critic_input.quest_states]}

=== SPECIALIST PROPOSALS ===
{_fmt_npc_check(critic_input)}

{_fmt_lore_check(critic_input)}

{_fmt_quest_check(critic_input)}

{_fmt_rules_check(critic_input)}

=== PRE-COMPUTED STRUCTURAL ISSUES ===
{chr(10).join('- [' + i.severity.upper() + '] ' + i.description for i in deterministic_issues) if deterministic_issues else "None"}

=== VALIDATION TASK ===
Check each proposal above. Pay special attention to:
1. Does the NPC's speech mention facts, names, or events NOT in their authorized knowledge list?
2. Does the lore summary introduce facts that contradict the established world facts?
3. Do the quest updates make logical sense given the player action?

Include the pre-computed structural issues in your issues list if they are non-trivial.
Return your verdict, the full list of issues, and a one-sentence summary.
"""

    result = await _critic_agent.run(prompt)
    output = result.output

    # Ensure deterministic error-level issues always force the verdict to reject
    has_deterministic_error = any(i.severity == "error" for i in deterministic_issues)
    if has_deterministic_error and output.verdict == "approve":
        output = CriticOutput(
            verdict="reject",
            issues=deterministic_issues + output.issues,
            summary=output.summary,
            suggested_corrections=output.suggested_corrections,
        )
    elif deterministic_issues:
        # Merge deterministic issues into LLM output without duplicating
        existing_descriptions = {i.description for i in output.issues}
        merged = list(output.issues)
        for di in deterministic_issues:
            if di.description not in existing_descriptions:
                merged.append(di)
        output = CriticOutput(
            verdict=output.verdict,
            issues=merged,
            summary=output.summary,
            suggested_corrections=output.suggested_corrections,
        )

    return output


def fallback_critic_output() -> CriticOutput:
    """Safe fallback when the critic itself fails or times out."""
    return CriticOutput(
        verdict="approve",
        issues=[
            CriticIssue(
                issue_type="other",
                severity="info",
                description="Critic agent did not complete — proposals passed without validation.",
                agent_source="critic_agent",
            )
        ],
        summary="Critic unavailable. Proposals approved by default.",
    )
