from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

from src.models.state_models import GameState


RouteLabel = Literal[
    "dialogue",
    "exploration",
    "combat",
    "quest_progression",
    "lore_query",
    "mixed_action",
]


class RouteDecision(BaseModel):
    route: RouteLabel
    next_nodes: List[str] = Field(default_factory=list)
    reason: str


DIALOGUE_KEYWORDS = {
    "ask", "say", "tell", "speak", "talk", "persuade", "convince",
    "threaten", "greet", "question", "reply", "negotiate",
    "approach", "sit", "join", "wave", "nod",
}

EXPLORATION_KEYWORDS = {
    "look", "search", "explore", "inspect", "investigate", "examine",
    "move", "travel", "go", "enter", "follow", "check"
}

COMBAT_KEYWORDS = {
    "attack", "hit", "strike", "shoot", "fight", "kill", "stab",
    "slash", "punch", "defend", "block", "dodge"
}

LORE_KEYWORDS = {
    "who", "what", "where", "when", "why", "history", "legend",
    "rumor", "faction", "village", "ruins", "world"
}

QUEST_KEYWORDS = {
    "quest", "objective", "mission", "job", "task", "reward",
    "caravan", "missing", "deliver", "report", "complete"
}


def _tokenize(text: str) -> set[str]:
    return {word.strip(".,!?;:()[]{}\"'").lower() for word in text.split()}


def _contains_any(tokens: set[str], keywords: set[str]) -> bool:
    return any(token in keywords for token in tokens)


def classify_route(player_action: str, state: GameState) -> RouteDecision:
    """
    Classify the player action into a route and recommend next node(s).
    This version is still deterministic, but it is less eager to label
    actions as mixed unless the action truly combines distinct intents.
    """
    text = player_action.strip()
    text_lower = text.lower()
    tokens = _tokenize(text)

    is_dialogue = _contains_any(tokens, DIALOGUE_KEYWORDS)
    is_exploration = _contains_any(tokens, EXPLORATION_KEYWORDS)
    is_combat = _contains_any(tokens, COMBAT_KEYWORDS)
    is_lore = _contains_any(tokens, LORE_KEYWORDS)
    is_quest = _contains_any(tokens, QUEST_KEYWORDS)

    is_question = text.endswith("?") or any(
        text_lower.startswith(q) for q in ["what", "who", "where", "when", "why", "how"]
    )

    # Treat lore as a true lore query mainly when the player is asking a question
    is_true_lore_query = is_lore and is_question

    # Exploration and lore often overlap in wording, but that should not
    # automatically become a mixed route.
    if is_combat and (is_dialogue or is_exploration or is_quest):
        next_nodes = ["rules_agent"]
        if is_dialogue:
            next_nodes.append("npc_agent")
        if is_quest:
            next_nodes.append("quest_agent")
        return RouteDecision(
            route="mixed_action",
            next_nodes=next_nodes,
            reason="Player action combines combat with another major intent.",
        )

    if is_dialogue and is_quest:
        return RouteDecision(
            route="mixed_action",
            next_nodes=["npc_agent", "quest_agent"],
            reason="Player action combines conversation with quest-related intent.",
        )

    if is_combat:
        return RouteDecision(
            route="combat",
            next_nodes=["rules_agent"],
            reason="Player action contains combat-oriented language.",
        )

    if is_dialogue:
        return RouteDecision(
            route="dialogue",
            next_nodes=["npc_agent"],
            reason="Player action appears to be directed at a character or conversation.",
        )

    if is_true_lore_query:
        return RouteDecision(
            route="lore_query",
            next_nodes=["lore_agent"],
            reason="Player action appears to request world or setting knowledge.",
        )

    if is_exploration:
        return RouteDecision(
            route="exploration",
            next_nodes=["lore_agent"],
            reason="Player action appears to focus on movement, searching, or environment interaction.",
        )

    if is_quest:
        return RouteDecision(
            route="quest_progression",
            next_nodes=["quest_agent"],
            reason="Player action appears tied to a quest objective or mission progress.",
        )

    return RouteDecision(
        route="exploration",
        next_nodes=["lore_agent"],
        reason="No strong route match found, defaulting to exploration.",
    )