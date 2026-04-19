from src.orchestrator import run_turn
from src.state_manager import build_initial_state


def test_orchestrator_builds_execution_plan():
    state = build_initial_state(session_id="test_orch_001")

    result = run_turn(
        state,
        "I ask the innkeeper what she knows about the missing caravan."
    )

    assert result.selected_route == "mixed_action"
    assert result.execution_plan == ["npc_agent", "quest_agent"]
    assert result.aborted is False


def test_orchestrator_handles_failure_and_abort():
    state = build_initial_state(session_id="test_orch_002")

    result = run_turn(
        state,
        "I ask the innkeeper what she knows about the missing caravan.",
        fail_nodes=["npc_agent"],
    )

    assert result.aborted is True
    assert result.abort_reason is not None
    assert any(item.status == "failed" for item in result.execution_results)