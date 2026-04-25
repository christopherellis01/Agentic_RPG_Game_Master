import importlib

from fastapi.testclient import TestClient


def test_combat_turn_updates_goblin_hp():
    import src.api as api

    importlib.reload(api)

    client = TestClient(api.app)

    reset_response = client.post("/reset")
    assert reset_response.status_code == 200

    initial_state = client.get("/state").json()
    initial_goblin = initial_state["combatants"][0]

    assert initial_goblin["id"] == "goblin"
    assert initial_goblin["hp"] == 15
    assert initial_goblin["max_hp"] == 15

    turn_response = client.post(
        "/turn",
        json={
            "player_action": "I attack the goblin with my sword.",
            "target_npc_id": None,
        },
    )

    assert turn_response.status_code == 200

    turn_data = turn_response.json()

    assert turn_data["route"] == "combat"
    assert turn_data["rules"] is not None

    rules_payload = turn_data["rules"]
    damage_dealt = rules_payload["damage_dealt"]

    state_after_turn = client.get("/state").json()
    goblin_after_turn = state_after_turn["combatants"][0]

    expected_hp = max(15 - damage_dealt, 0)

    assert goblin_after_turn["hp"] == expected_hp

    activity_names = [item["name"] for item in turn_data["agent_activity"]]

    assert "router" in activity_names
    assert "rules" in activity_names
    assert "state" in activity_names
    assert "narrator" in activity_names