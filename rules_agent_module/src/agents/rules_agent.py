import random
from typing import Dict


def resolve_action(player_action: str, state: Dict) -> Dict:
    action = player_action.lower()

    if "attack" in action:
        roll = random.randint(1, 10)
        enemy_hp = state.get("enemy_hp", 20)

        if roll > 7:
            damage = 10
            outcome = "success"
        elif roll > 4:
            damage = 5
            outcome = "partial_success"
        else:
            damage = 0
            outcome = "failure"

        return {
            "action_type": "combat",
            "outcome": outcome,
            "reason": f"Roll = {roll}",
            "consequence": {
                "enemy_hp_change": -damage,
                "new_enemy_hp": enemy_hp - damage,
            },
        }

    if "persuade" in action or "convince" in action or "ask" in action:
        return {
            "action_type": "dialogue",
            "outcome": "partial_success",
            "reason": "The NPC listens but remains cautious.",
            "consequence": {"npc_attitude": "uncertain"},
        }

    if "search" in action or "inspect" in action or "look" in action:
        return {
            "action_type": "exploration",
            "outcome": "success",
            "reason": "You searched the area and found something useful.",
            "consequence": {"discovery": "hidden clue"},
        }

    return {
        "action_type": "unknown",
        "outcome": "failure",
        "reason": "Action not recognized.",
        "consequence": {},
    }
