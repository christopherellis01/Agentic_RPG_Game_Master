from src.state_manager import build_initial_state


def test_initial_state_builds_successfully():
    state = build_initial_state(session_id="test_state_001")

    assert state.meta.session_id == "test_state_001"
    assert state.meta.turn_id == 1
    assert state.canonical.location is not None
    assert state.turn.player_action == "The player enters the world."