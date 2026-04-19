from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.state_models import EventRecord, GameState
from src.router import RouteDecision, classify_route
from src.state_manager import start_new_turn


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