# Agentic_RPG_Game_Master
An agentic AI Game Master for lightweight tabletop RPG sessions - group project for CAP6640

Agentic Game RPG Master is a multi-agent AI system designed to run and adapt a lightweight tabletop RPG session in real time. Instead of relying on a single model to handle everything, the system uses a central supervisor with conditional routing to coordinate specialized components for world lore, NPC behavior, quest progression, rules resolution, continuity checking, state updates, and final narration.

The goal of the project is to create a game experience that feels like a living dungeon master team. The system should be able to respond to player choices, maintain continuity across turns, preserve structured game state, and produce coherent, player-facing narrative output. This project is being developed in Python with Jupyter notebook-based prototyping, using structured JSON-style data and a graph-based orchestration approach inspired by LangGraph.

---

> This repository now contains a working prototype structure with routing, orchestration, state management, specialist agents, deterministic rules resolution, notebook-based demos, and pytest coverage. Development is still ongoing, but the core project pieces are now implemented and testable..

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

A tabletop RPG session is not just one task. It requires managing multiple interdependent tasks simultaneously: narration, rules resolution, world knowledge, NPC behavior, quest logic, and long-term continuity across turns. A single LLM can attempt to handle all of these, but it quickly becomes unreliable—hallucinating inconsistent rules, forgetting prior events, mixing incompatible world facts, or generating unplayable scenarios as the session grows longer.

This project uses a supervisor-plus-specialists architecture to decompose the problem into bounded responsibilities with clear handoffs. Deterministic Python components manage orchestration, routing, state updates, and validation, while LLM-backed specialists handle interpretation-heavy tasks like dialogue generation, quest interpretation, and narrative synthesis. The result is a system that maintains coherent world state across many turns, enforces consistent rules, preserves NPC memory and relationships, and produces structured outputs that can be validated before committing changes—capabilities that emerge naturally from coordination rather than from a single model's internal reasoning.

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

```text
Agentic_RPG_Game_Master/
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
```
---

## Tech stack

- **Python**
- **Jupyter Notebook / VS Code**
- **Pydantic** for structured models and validation
- **PydanticAI** for LLM-backed specialist agents
- **JSON / structured data** for world data, NPCs, quests, and rules
- **Pytest** for testing routing, orchestration, state logic, and rules behavior
- **FastAPI / Uvicorn** for optional local web-serving or API development

---

## Setup

Clone the repository and move into the project folder:

```
git clone https://github.com/christopherellis01/Agentic_RPG_Game_Master.git
cd Agentic_RPG_Game_Master
```

Create and activate a virtual environment:

```
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Register the Jupyter kernel:

```
python -m ipykernel install --user --name=agentic_rpg_venv --display-name "Python (agentic_rpg_venv)"
```

## Running the Project

The easiest development entry point is the notebook prototype:

```
jupyter lab
```

Then open:

```
notebooks/prototype_game_loop.ipynb
```

The project also includes an HTML demo in the demo/ folder. To serve it locally, run this from the repository root:

```
python -m http.server 8000
```

Then open:

```
http://localhost:8000/demo/shattered_vale_demo.html
```

Avoid opening the HTML file directly with a file:/// browser path, because it may not be able to access related project files correctly.


As the project matures, the main orchestration flow can also be run through Python modules in `src/`.

---

## Current status

The project has moved beyond the initial scaffolding phase. Current implemented pieces include:

- router logic for classifying player actions and selecting agent paths
- an orchestrator skeleton for managing turn flow
- structured state models and state manager logic
- specialist agents for lore, NPC behavior, quests, and rules resolution
- an integrated Rules Agent with deterministic handling for combat, dialogue, and exploration actions
- a compatibility layer for the standalone rules agent module
- notebook-based prototyping
- pytest coverage for routing, orchestration, state management, and rules behavior
- structured State Updater support using `StatePatch` objects
- canonical combatant state with persistent HP tracking
- demo API support for combat turns that update and remember Goblin HP
- API-level test coverage for combat state persistence

Current test status:

```
python -m pytest
```

Expected Result

```
15 passed
```

The next development focus is confirming a complete playable turn through the notebook or demo flow, from player input through routing, agent resolution, state update, and final narration.


### State Updater and persistent combat state

The demo API now includes a structured State Updater that applies approved state patches to canonical game state. Combatant state has been added to the canonical model, including a seeded Goblin encounter used for combat testing.

Combat turns now follow this flow:

```
Player action
→ Router selects combat
→ Rules Agent resolves the attack
→ State Updater applies combatant HP changes
→ Narrator produces a player-facing response
→ Updated state persists across turns
```
For example, if the Rules Agent resolves an attack that deals 10 damage, the State Updater changes the Goblin’s HP from 15 to 5, and the next turn starts from that updated HP instead of resetting to 15.

This behavior is covered by an API test in:

```
tests/test_api_combat_state.py
```

---

## Rules Agent integration note

The Rules Agent is now integrated into the async turn orchestration flow. A combat player action can be routed to the Rules Agent, resolved through deterministic rules logic, and stored as structured specialist output with proposed state changes for later validation and state update.

Example verified flow:

```
Player action: "I attack the goblin with my sword."
Selected route: combat
Execution plan: ['rules_agent']
Rules Agent output: combat success with structured damage and proposed state changes
```

This confirms that the Rules Agent is not only passing isolated tests, but is also being called during an actual game-turn flow.

---

## Team

Mazin Bashir  
Christopher Ellis  
Agnes Sithole  

---

## Future Improvements

- richer NPC memory and relationship tracking
- more advanced branching quests
- better combat balancing
- expanded world data
- improved debugging and turn tracing
- optional UI or web front end
- better combat balancing and expanded encounter state
