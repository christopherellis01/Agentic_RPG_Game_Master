from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.state_models import EventRecord, GameState
from src.router import RouteDecision, classify_route
from src.state_manager import start_new_turn

from src.models.state_models import SpecialistOutput
from src.agents.rules_agent import RulesAgentInput, run_rules_agent

class NodeExecutionResult(BaseModel):
    """
    Represents the result of executing one planned node.
    """
    node_name: str
    status: str
    summary: str
    attempts: int = 1


class OrchestrationResult(BaseModel):
    """
    Container for the result of one orchestration pass.
    """
    player_action: str
    selected_route: str
    next_nodes: List[str] = Field(default_factory=list)
    execution_plan: List[str] = Field(default_factory=list)
    execution_results: List[NodeExecutionResult] = Field(default_factory=list)
    reason: str
    aborted: bool = False
    abort_reason: Optional[str] = None
    state: GameState


def build_execution_plan(decision: RouteDecision) -> List[str]:
    """
    Return the ordered node sequence for the selected route.

    For now, this simply mirrors the router's recommended next_nodes.
    Later, this is where you can enforce more explicit sequencing rules.
    """
    return decision.next_nodes.copy()


def execute_planned_nodes(
    state: GameState,
    execution_plan: List[str],
    fail_nodes: Optional[List[str]] = None,
) -> tuple[List[NodeExecutionResult], bool, Optional[str]]:
    """
    Execute planned nodes using placeholder behavior with basic retry/fallback flow.

    If a node appears in fail_nodes, this function simulates failure and retries
    until max_retries is reached. If retries are exhausted, execution aborts.
    """
    results: List[NodeExecutionResult] = []
    fail_nodes = fail_nodes or []

    for node_name in execution_plan:
        attempt_count = 0
        completed = False

        while attempt_count <= state.meta.max_retries:
            attempt_count += 1

            if node_name in fail_nodes:
                state.meta.retry_count += 1

                state.turn.current_turn_events.append(
                    EventRecord(
                        event_type="node_retry",
                        summary=(
                            f"{node_name} failed on attempt {attempt_count}. "
                            f"Retry count is now {state.meta.retry_count}."
                        ),
                        source_node="orchestrator",
                    )
                )

                if attempt_count > state.meta.max_retries:
                    result = NodeExecutionResult(
                        node_name=node_name,
                        status="failed",
                        summary=(
                            f"{node_name} failed after {attempt_count - 1} retries. "
                            f"Execution aborted."
                        ),
                        attempts=attempt_count - 1,
                    )
                    results.append(result)

                    abort_reason = (
                        f"{node_name} exceeded max retries "
                        f"({state.meta.max_retries})."
                    )

                    state.turn.current_turn_events.append(
                        EventRecord(
                            event_type="execution_aborted",
                            summary=abort_reason,
                            source_node="orchestrator",
                        )
                    )

                    return results, True, abort_reason

            else:
                result = NodeExecutionResult(
                    node_name=node_name,
                    status="completed",
                    summary=f"Placeholder execution completed for {node_name}.",
                    attempts=attempt_count,
                )
                results.append(result)

                state.turn.current_turn_events.append(
                    EventRecord(
                        event_type="node_executed",
                        summary=f"{node_name} executed with placeholder behavior.",
                        source_node="orchestrator",
                    )
                )

                completed = True
                break

        if not completed and node_name not in fail_nodes:
            # Defensive fallback; should not normally happen.
            abort_reason = f"{node_name} did not complete for an unknown reason."
            state.turn.current_turn_events.append(
                EventRecord(
                    event_type="execution_aborted",
                    summary=abort_reason,
                    source_node="orchestrator",
                )
            )
            return results, True, abort_reason

    return results, False, None


async def execute_planned_nodes_async(
    state: GameState,
    execution_plan: List[str],
    fail_nodes: Optional[List[str]] = None,
) -> tuple[List[NodeExecutionResult], bool, Optional[str]]:
    """
    Execute planned nodes for a real game turn.

    This async version can call LLM-backed specialist agents.
    For now, rules_agent is integrated; other agents still use placeholder behavior.
    """
    results: List[NodeExecutionResult] = []
    fail_nodes = fail_nodes or []

    for node_name in execution_plan:
        attempt_count = 0

        while attempt_count <= state.meta.max_retries:
            attempt_count += 1

            if node_name in fail_nodes:
                state.meta.retry_count += 1
                state.turn.current_turn_events.append(
                    EventRecord(
                        event_type="node_retry",
                        summary=(
                            f"{node_name} failed on attempt {attempt_count}. "
                            f"Retry count is now {state.meta.retry_count}."
                        ),
                        source_node="orchestrator",
                    )
                )

                if attempt_count > state.meta.max_retries:
                    result = NodeExecutionResult(
                        node_name=node_name,
                        status="failed",
                        summary=(
                            f"{node_name} failed after {attempt_count - 1} retries. "
                            f"Execution aborted."
                        ),
                        attempts=attempt_count - 1,
                    )
                    results.append(result)

                    abort_reason = (
                        f"{node_name} exceeded max retries "
                        f"({state.meta.max_retries})."
                    )

                    state.turn.current_turn_events.append(
                        EventRecord(
                            event_type="execution_aborted",
                            summary=abort_reason,
                            source_node="orchestrator",
                        )
                    )

                    return results, True, abort_reason

                continue

            if node_name == "rules_agent":
                rules_input = RulesAgentInput(
                    player_action=state.turn.player_action,
                    current_scene=state.canonical.current_scene,
                    character_hp=state.canonical.party_status.hp,
                    character_max_hp=state.canonical.party_status.max_hp,
                    relevant_stats=[],
                    inventory=state.canonical.inventory,
                    rules_summary=(
                        "Use simple d10-style resolution. "
                        "High rolls succeed, middle rolls partially succeed, low rolls fail. "
                        "Agents may propose state changes but must not commit them directly."
                    ),
                    difficulty="medium",
                    enemy_name="Goblin",
                    enemy_hp=15,
                )

                rules_output = await run_rules_agent(rules_input)

                state.turn.specialist_outputs.append(
                    SpecialistOutput(
                        node_name="rules_agent",
                        summary=rules_output.mechanical_summary,
                        structured_data=rules_output.model_dump(),
                    )
                )

                state.turn.current_turn_events.append(
                    EventRecord(
                        event_type="node_executed",
                        summary="rules_agent executed using integrated Rules Agent logic.",
                        source_node="rules_agent",
                    )
                )

                results.append(
                    NodeExecutionResult(
                        node_name="rules_agent",
                        status="completed",
                        summary=rules_output.mechanical_summary,
                        attempts=attempt_count,
                    )
                )

                break

            # Placeholder behavior for agents not fully integrated yet.
            results.append(
                NodeExecutionResult(
                    node_name=node_name,
                    status="completed",
                    summary=f"Placeholder execution completed for {node_name}.",
                    attempts=attempt_count,
                )
            )

            state.turn.current_turn_events.append(
                EventRecord(
                    event_type="node_executed",
                    summary=f"{node_name} executed with placeholder behavior.",
                    source_node="orchestrator",
                )
            )

            break

    return results, False, None


def run_turn(
    state: GameState,
    player_action: str,
    fail_nodes: Optional[List[str]] = None,
) -> OrchestrationResult:
    """
    Main orchestration entry point for a single player turn.

    This version:
    1. Starts a new turn
    2. Classifies the route
    3. Stores the routing decision in state
    4. Builds an execution plan
    5. Executes placeholder nodes with retry/fallback behavior
    6. Records orchestration events
    7. Returns the orchestration result
    """
    # Reset turn state and advance metadata
    state = start_new_turn(state, player_action)

    # Route the player action
    decision: RouteDecision = classify_route(player_action, state)

    # Store selected route in transient turn state
    state.turn.selected_route = decision.route

    # Build execution plan
    execution_plan = build_execution_plan(decision)

    # Record routing events
    state.turn.current_turn_events.append(
        EventRecord(
            event_type="route_selected",
            summary=f"Route '{decision.route}' selected with nodes {decision.next_nodes}.",
            source_node="orchestrator",
        )
    )

    state.turn.current_turn_events.append(
        EventRecord(
            event_type="route_reason",
            summary=decision.reason,
            source_node="router",
        )
    )

    state.turn.current_turn_events.append(
        EventRecord(
            event_type="execution_plan_built",
            summary=f"Execution plan created: {execution_plan}",
            source_node="orchestrator",
        )
    )

    # Execute placeholder nodes with retry/fallback flow
    execution_results, aborted, abort_reason = execute_planned_nodes(
        state=state,
        execution_plan=execution_plan,
        fail_nodes=fail_nodes,
    )

    return OrchestrationResult(
        player_action=player_action,
        selected_route=decision.route,
        next_nodes=decision.next_nodes,
        execution_plan=execution_plan,
        execution_results=execution_results,
        reason=decision.reason,
        aborted=aborted,
        abort_reason=abort_reason,
        state=state,
    )

async def run_turn_async(
    state: GameState,
    player_action: str,
    fail_nodes: Optional[List[str]] = None,
) -> OrchestrationResult:
    """
    Async orchestration entry point for a real single player turn.

    This version can call async specialist agents such as run_rules_agent().
    """
    state = start_new_turn(state, player_action)

    decision: RouteDecision = classify_route(player_action, state)

    state.turn.selected_route = decision.route

    execution_plan = build_execution_plan(decision)

    state.turn.current_turn_events.append(
        EventRecord(
            event_type="route_selected",
            summary=f"Route '{decision.route}' selected with nodes {decision.next_nodes}.",
            source_node="orchestrator",
        )
    )

    state.turn.current_turn_events.append(
        EventRecord(
            event_type="route_reason",
            summary=decision.reason,
            source_node="router",
        )
    )

    state.turn.current_turn_events.append(
        EventRecord(
            event_type="execution_plan_built",
            summary=f"Execution plan created: {execution_plan}",
            source_node="orchestrator",
        )
    )

    execution_results, aborted, abort_reason = await execute_planned_nodes_async(
        state=state,
        execution_plan=execution_plan,
        fail_nodes=fail_nodes,
    )

    return OrchestrationResult(
        player_action=player_action,
        selected_route=decision.route,
        next_nodes=decision.next_nodes,
        execution_plan=execution_plan,
        execution_results=execution_results,
        reason=decision.reason,
        aborted=aborted,
        abort_reason=abort_reason,
        state=state,
    )