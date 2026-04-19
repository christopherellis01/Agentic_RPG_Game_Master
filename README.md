# Agentic_RPG_Game_Master
An agentic AI Game Master for small RPG games - group project for CAP6640

Agentic Game RPG Master is a multi-agent AI system designed to run and adapt a lightweight tabletop RPG session in real time. Instead of relying on a single model to handle everything, the system uses a central supervisor with conditional routing to coordinate specialized components for world lore, NPC behavior, quest progression, rules resolution, continuity checking, state updates, and final narration.

The goal of the project is to create a game experience that feels like a living dungeon master team. The system should be able to respond to player choices, maintain continuity across turns, preserve structured game state, and produce coherent, player-facing narrative output. This project is being developed in Python with Jupyter Notebook support, using structured JSON-style data and a graph-based orchestration approach inspired by LangGraph.

---

## Project goals

- Build a supervisor-driven multi-agent RPG workflow
- Maintain consistent world state across many turns
- Use specialized components for bounded tasks instead of one free-form agent
- Support branching choices, NPC interaction, basic combat, and quest progression
- Keep game content in structured data formats instead of burying everything inside prompts
- Make the system inspectable, testable, and easier to debug

---

## Why a multi-agent approach?

A tabletop RPG session is not just one task. It mixes narration, rules resolution, world knowledge, NPC behavior, quest logic, and continuity tracking. A single model can try to do all of that, but it becomes harder to control, harder to debug, and more likely to drift over time.

This project uses a supervisor-plus-specialists architecture so each part of the turn can be handled more cleanly. Deterministic Python components manage orchestration, routing, and state updates, while LLM-backed specialists handle bounded tasks that benefit from interpretation and generation. That separation makes the system more reliable and easier to reason about.

---

## High-level architecture

At a high level, the turn loop works like this:

`player turn -> supervisor -> router -> one or more specialist nodes -> critic -> state updater -> narrator`

Core components include:

- **Supervisor / Orchestrator** — manages the overall turn lifecycle and global turn state machine
- **Router** — classifies the player action and recommends the next execution path
- **World / Lore Agent** — handles setting knowledge and environmental context
- **NPC Agent** — handles character dialogue, motives, and reactions
- **Quest Agent** — tracks objectives, branching, and consequences
- **Rules / Resolution Agent** — resolves uncertain actions, combat, and skill checks
- **Continuity / Critic Agent** — validates proposed outcomes before state updates
- **State Updater** — the only component allowed to modify canonical game state
- **Narrator / Response Agent** — converts approved outcomes into player-facing text

For the full system design, see [docs/architecture.md](docs/architecture.md).

---

## Design principles

- **Centralized control:** the Supervisor remains the final authority for routing, retries, fallback behavior, and safe turn termination
- **Single-writer state updates:** only the State Updater can commit changes to canonical game state
- **Structured memory:** world data, NPCs, quests, rules, and state are stored in structured formats
- **Validation before mutation:** specialist outputs are checked by the Critic before any state changes are committed
- **Bounded retry behavior:** repair and retry loops should be explicit, limited, and observable

---

## Repository structure

```text id="k6k1oy"
agentic-game-rpg-master/
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   └── architecture.md
├── data/
│   ├── world/
│   ├── npcs/
│   ├── quests/
│   ├── rules/
│   └── schemas/
├── notebooks/
│   └── prototype_game_loop.ipynb
├── src/
│   ├── orchestrator.py
│   ├── router.py
│   ├── state_manager.py
│   ├── critic.py
│   ├── narrator.py
│   └── agents/
│       ├── lore_agent.py
│       ├── npc_agent.py
│       ├── quest_agent.py
│       └── rules_agent.py
└── tests/
