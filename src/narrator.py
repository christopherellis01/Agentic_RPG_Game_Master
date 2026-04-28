from src.models.state_models import SpecialistOutput


def narrate_turn(player_action: str, specialist_outputs: list[SpecialistOutput]) -> str:
    if not specialist_outputs:
        return "Nothing significant happens yet."

    rules_outputs = [o for o in specialist_outputs if o.node_name == "rules_agent"]

    if rules_outputs:
        rules_data = rules_outputs[-1].structured_data
        outcome = rules_data.get("outcome", "unknown")
        damage = rules_data.get("damage_dealt", 0)

        if outcome == "success" and damage > 0:
            return (
                f"You follow through on your action: {player_action} "
                f"The strike lands cleanly, dealing {damage} damage."
            )
        if outcome == "partial_success" and damage > 0:
            return (
                f"You attempt: {player_action} "
                f"It only partly works, but you still deal {damage} damage."
            )
        if outcome == "failure":
            return f"You attempt: {player_action} but it does not succeed this time."

    return specialist_outputs[-1].summary
