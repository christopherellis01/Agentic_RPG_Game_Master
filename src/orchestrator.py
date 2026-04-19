from __future__ import annotations

from typing import List

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
) -> List[NodeExecutionResult]:
    """
    Execute planned nodes using placeholder behavior.

    This version does not call real agents yet. It only simulates node
    execution so the orchestration flow can be tested end-to-end.
    """
    results: List[NodeExecutionResult] = []

    for node_name in execution_plan:
        result = NodeExecutionResult(
            node_name=node_name,
            status="completed",
            summary=f"Placeholder execution completed for {node_name}.",
        )
        results.append(result)

        state.turn.current_turn_events.append(
            EventRecord(
                event_type="node_executed",
                summary=f"{node_name} executed with placeholder behavior.",
                source_node="orchestrator",
            )
        )

    return results


def run_turn(state: GameState, player_action: str) -> OrchestrationResult:
    """
    Main orchestration entry point for a single player turn.

    This version:
    1. Starts a new turn
    2. Classifies the route
    3. Stores the routing decision in state
    4. Builds an execution plan
    5. Executes placeholder nodes
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

    # Execute placeholder nodes
    execution_results = execute_planned_nodes(state, execution_plan)

    return OrchestrationResult(
        player_action=player_action,
        selected_route=decision.route,
        next_nodes=decision.next_nodes,
        execution_plan=execution_plan,
        execution_results=execution_results,
        reason=decision.reason,
        state=state,
    )