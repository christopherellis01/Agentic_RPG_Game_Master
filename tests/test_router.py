from src.router import classify_route
from src.state_manager import build_initial_state


def test_dialogue_route():
    state = build_initial_state(session_id="test_router_001")
    result = classify_route("I talk to Marla.", state)

    assert result.route == "dialogue"
    assert result.next_nodes == ["npc_agent"]


def test_exploration_route():
    state = build_initial_state(session_id="test_router_002")
    result = classify_route("I explore the ruins and search for tracks.", state)

    assert result.route == "exploration"
    assert result.next_nodes == ["lore_agent"]


def test_combat_route():
    state = build_initial_state(session_id="test_router_003")
    result = classify_route("I attack the bandit with my sword.", state)

    assert result.route == "combat"
    assert result.next_nodes == ["rules_agent"]


def test_lore_route():
    state = build_initial_state(session_id="test_router_004")
    result = classify_route("What do I know about the history of these ruins?", state)

    assert result.route == "lore_query"
    assert result.next_nodes == ["lore_agent"]