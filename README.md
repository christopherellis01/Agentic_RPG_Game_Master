# Agentic_RPG_Game_Master
An agentic AI Game Master for lightweight tabletop RPG sessions - group project for CAP6640

Agentic Game RPG Master is a multi-agent AI system designed to run and adapt a lightweight tabletop RPG session in real time. Instead of relying on a single model to handle everything, the system uses a central supervisor with conditional routing to coordinate specialized components for world lore, NPC behavior, quest progression, rules resolution, continuity checking, state updates, and final narration.

The goal of the project is to create a game experience that feels like a living dungeon master team. The system should be able to respond to player choices, maintain continuity across turns, preserve structured game state, and produce coherent, player-facing narrative output. This project is being developed in Python with Jupyter notebook-based prototyping, using structured JSON-style data and a graph-based orchestration approach inspired by LangGraph.

---

>This repository currently contains project scaffolding and architecture documents; the first executable prototype is under active development.

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
- **LangGraph** for graph-based orchestration
- **Pydantic** for structured models and validation
- **JSON** for world data, NPCs, quests, and rules
- **Pytest** for testing routing and state logic

---

## Setup

Clone the repository and move into the project folder:

```
git clone https://github.com/christopherellis01/Agentic_RPG_Game_Master.git
cd agentic-game-rpg-master
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

For early development, the easiest entry point will likely be the notebook prototype:

```
jupyter lab
```

Then open:

```
notebooks/prototype_game_loop.ipynb
```

As the project matures, the main orchestration flow can also be run through Python modules in `src/`.

---

## Current status

This project is currently in the architecture and setup phase. The initial focus is on:

- defining structured game content
- implementing canonical and transient state models
- building the router and orchestrator skeleton
- stubbing specialist components
- testing one full turn from input to narration

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

