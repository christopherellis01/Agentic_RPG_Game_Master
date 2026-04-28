import importlib
import asyncio

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


def test_chrome_devtools_workspace_probe_is_quiet():
    import src.api as api

    importlib.reload(api)

    client = TestClient(api.app)

    response = client.get("/.well-known/appspecific/com.chrome.devtools.json")

    assert response.status_code == 200
    assert response.json() == {}


def test_npc_turn_uses_fallback_when_live_agent_times_out(monkeypatch):
    import src.api as api

    importlib.reload(api)
    monkeypatch.setattr(api, "AGENT_TIMEOUT_SECONDS", 0.01)

    async def slow_npc_agent(_agent_input):
        await asyncio.sleep(1)

    monkeypatch.setattr(api, "run_npc_agent", slow_npc_agent)

    client = TestClient(api.app)

    response = client.post(
        "/turn",
        json={
            "player_action": "I ask Mara what has been happening lately.",
            "target_npc_id": "mara_innkeeper",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["npc"] is not None
    assert "LOCAL FALLBACK" in data["npc"]["emotional_tone"]
    assert any(
        item["name"] == "npc" and "local fallback" in item["summary"]
        for item in data["agent_activity"]
    )


def test_npc_fallback_respects_character_voice():
    import src.api as api
    from src.agents.npc_agent import NPCAgentInput

    importlib.reload(api)

    mara = api._fallback_npc_output(
        NPCAgentInput(
            player_action="What is happening?",
            npc_name="Mara",
            npc_role="Innkeeper",
            npc_personality=["observant", "practical", "protective of regulars"],
            npc_goals=["Keep Oakshade's travelers safe and paying"],
            npc_disposition="wary but fair",
            relevant_memory=["Heard that a Council scout has not returned."],
        )
    )
    corvin = api._fallback_npc_output(
        NPCAgentInput(
            player_action="What is happening?",
            npc_name="Corvin",
            npc_role="Hooded traveler",
            npc_personality=["quiet", "guarded", "quick to size people up"],
            npc_goals=["Recruit an outsider to do the dangerous part of his investigation"],
            npc_disposition="neutral, attentive",
            relevant_memory=["Has a partial map of the Emberwood Ruins."],
        )
    )

    assert mara.speech != corvin.speech
    assert "clean cup" in mara.speech
    assert "hood" in corvin.speech
