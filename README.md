# Agentic RPG Game Master

A multi-agent AI Game Master for lightweight tabletop RPG sessions — CAP6640 group project.

---

## What this is

Agentic RPG Game Master is a supervisor-driven multi-agent system that runs a real-time tabletop RPG session. Instead of asking a single LLM to handle everything, the system routes each player turn through a pipeline of specialized agents — each with a narrow, bounded responsibility. Agents propose changes; a Critic validates those proposals before any state is committed.

The result is a game that maintains coherent world state across many turns, enforces consistent rules, preserves NPC memory, and produces narrative that stays grounded in the established fiction.

The project ships with a fully playable browser demo set in **The Shattered Vale**, a dark-fantasy mystery scenario.

---

## Why a multi-agent approach?

A tabletop RPG session requires managing several interdependent tasks simultaneously: narration, rules resolution, world knowledge, NPC behavior, quest logic, and continuity across turns. A single LLM can attempt all of these, but becomes unreliable at scale — hallucinating inconsistent rules, forgetting prior events, and generating unplayable scenarios.

This project decomposes the problem into bounded agents with clear handoffs. Deterministic Python components handle orchestration, routing, state updates, and validation. LLM-backed specialists handle interpretation-heavy tasks like dialogue generation, quest interpretation, and lore grounding. A dedicated Critic Agent validates every proposal before it reaches game state.

---

## Architecture

The turn loop:

```
player action
  → Router (classifies intent, selects agents)
  → Specialist Agents (propose changes — do not commit)
      ├── Lore Agent       — environmental context, world knowledge
      ├── NPC Agent        — character dialogue, motives, reactions
      ├── Quest Agent      — objectives, branching, consequences
      └── Rules Agent      — combat resolution, skill checks (d10 system)
  → Critic Agent           — validates all proposals before state mutation
  → State Updater          — the only component that writes to canonical state
  → Narrator               — converts approved outcomes to player-facing text
```

Key design principles:

- **Deferred mutation** — specialists produce `StatePatch` proposals; nothing is committed until the Critic approves
- **Two-phase critic** — deterministic structural checks always run; an LLM semantic check fires only when NPC or lore proposals exist (keeps pure combat turns fast)
- **Single-writer state** — only the State Updater touches canonical game state
- **Graceful fallback** — every LLM agent has a timeout and a structured local fallback so the turn always completes

For the full design, see [docs/architecture.md](docs/architecture.md).

---

## Repository structure

```
Agentic_RPG_Game_Master/
├── README.md
├── requirements.txt
├── demo/
│   └── shattered_vale_demo.html   # live browser demo
├── docs/
│   ├── architecture.md
│   └── current_orchestration_flow.md
├── data/
│   ├── world/world_state.json
│   ├── npcs/npc_data.json
│   └── quests/quest_data.json
├── notebooks/
│   └── knowledge_layer_demo.ipynb
├── src/
│   ├── api.py                     # FastAPI server + turn orchestration
│   ├── router.py                  # action classification
│   ├── state_manager.py
│   ├── state_updater.py
│   ├── retrieval.py
│   ├── narrator.py
│   └── agents/
│       ├── critic_agent.py
│       ├── lore_agent.py
│       ├── npc_agent.py
│       ├── quest_agent.py
│       └── rules_agent.py
├── rules_agent_module/            # standalone rules agent module
└── tests/
    ├── test_api_combat_state.py
    ├── test_critic_agent.py
    ├── test_orchestrator.py
    ├── test_router.py
    └── test_state_manager.py
```

---

## Tech stack

| Layer | Tool |
|---|---|
| Agent framework | PydanticAI |
| Validation / models | Pydantic v2 |
| LLM backend | Claude (`claude-sonnet-4-6`) via LiteLLM |
| API server | FastAPI + Uvicorn |
| Testing | Pytest + anyio |
| Notebooks | Jupyter |

---

## Setup

**Prerequisites:** Python 3.11+, a `CAP6640_API_KEY` environment variable pointing to the course LLM endpoint.

Clone and enter the project:

```bash
git clone https://github.com/christopherellis01/Agentic_RPG_Game_Master.git
cd Agentic_RPG_Game_Master
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Set your API key:

```bash
export CAP6640_API_KEY=your_key_here
```

---

## Running the demo

Start the FastAPI server from the project root:

```bash
uvicorn src.api:app --reload --port 8000
```

Then open your browser to:

```
http://localhost:8000
```

The demo loads **The Shattered Vale** — a dark inn in a village on the edge of crisis. You can talk to NPCs, investigate the environment, fight the goblin, and advance the quest. Every agent's activity is shown live on the right panel, including the Critic's verdict each turn.

Available pre-built actions are listed in the demo UI. You can also type free-form commands in the input box.

---

## Running the tests

```bash
python -m pytest -v
```

Expected output:

```
29 passed
```

The test suite covers routing logic, orchestration, state management, rules resolution, the Critic Agent (deterministic and API-level), and combat state persistence.

---

## The Critic Agent

The Critic is the validation layer between specialist proposals and state commit. It runs every turn and checks for:

| Issue type | Example |
|---|---|
| `knowledge_leak` | NPC references a fact not in their authorized knowledge list |
| `lore_contradiction` | Lore summary contradicts an established world fact |
| `illegal_transition` | Quest agent tries to complete an already-completed objective |
| `invalid_combat` | Rules agent proposes damage to an already-defeated enemy |
| `npc_behavior_violation` | Hostile NPC suddenly responds with a friendly tone |

**Verdict:** `approve` / `warn` / `reject`

A `reject` blocks all `StatePatch` objects from being applied. The player sees the Critic's summary in the agent activity panel and in the dialogue feed.

Deterministic checks always run (fast, no LLM cost). The LLM semantic check fires only when an NPC or lore proposal is present. Pure combat turns skip the LLM check entirely.

---

## Dice resolution

Combat actions use a d10 hit roll with variable damage:

| Roll | Result | Damage |
|---|---|---|
| 8–10 | Success | 6–10 (random) |
| 5–7 | Partial success | 2–5 (random) |
| 1–4 | Failure | 0 |

The roll value is shown inline in the dialogue feed (`[Roll: 7/10]`) and in the Rules Agent activity entry (`RULES · d10=7`).

---

## Team

Mazin Bashir  
Christopher Ellis  
Agnes Sithole

---

## Future improvements

- Richer NPC memory and relationship tracking across turns
- More advanced branching quest trees
- Expanded world data and encounter variety
- Session persistence (save / load game state)
- Improved combat balancing and multi-enemy encounters
