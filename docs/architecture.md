# ARCHITECTURE NOTE — AGENTIC GAME RPG MASTER

## Overview

Agentic Game RPG Master is a multi-agent storytelling system that runs a lightweight tabletop RPG session through a controlled orchestration loop. Rather than letting agents communicate freely, the system uses a central supervisor architecture in which a deterministic orchestration layer routes each player turn to the appropriate specialist component, collects structured outputs, validates proposed changes, updates shared game state, and returns a final narrative response to the player. :contentReference[oaicite:0]{index=0}

This project uses a supervisor-plus-specialists design with conditional routing because centralized control is easier to debug, more reliable for shared-state consistency, and safer than open-ended agent-to-agent conversation in workflows with interdependent steps and persistent memory. The core loop is:

`player turn -> classify action type and required resolution path -> route to one or more specialist nodes -> validate proposals -> commit approved state changes -> generate player-facing response` :contentReference[oaicite:1]{index=1}

This architecture maps well to LangGraph, where the system is modeled as a graph over shared state, nodes represent deterministic components or LLM-backed specialist agents, and conditional edges encode routing decisions based on the current turn and game context. :contentReference[oaicite:2]{index=2}

## Design principle

The architecture follows a hybrid control model: :contentReference[oaicite:3]{index=3}

- Deterministic Python components handle orchestration, routing, state mutation, and guardrails.
- LLM-backed specialist agents handle bounded tasks that require interpretation, generation, or critique.

This separation improves reliability by keeping flow control and canonical state updates deterministic while reserving LLM calls for tasks where flexible reasoning or narrative generation adds value. :contentReference[oaicite:4]{index=4}

## Core components

### Supervisor / Orchestrator

**Type:** Deterministic Python component

**Purpose:**  
Central controller for the full turn lifecycle.

**Input received:**

- Player action text
- Relevant state snapshot
- Recent turn history
- Routing policy
- Route recommendation from the Router

**Output returned:**

- Ordered execution plan for the turn
- Next node to invoke
- Final packaged turn result when the turn is complete

**Responsibilities:**

- Manage the overall turn lifecycle
- Maintain the global turn state machine
- Enforce the order of operations
- Decide whether to follow the recommended route, invoke one or more specialist nodes in sequence, retry, fall back, or terminate the turn
- Prevent unnecessary or duplicate node execution
- Pass narrowed state snapshots to downstream nodes
- Ensure only approved updates reach the State Updater
- Record selected route, invoked nodes, validation outcomes, committed state delta, and final response for debugging and auditability

### Router

**Type:** Deterministic Python component

**Purpose:**  
Classify the player turn and recommend the next execution path.

**Input received:**

- Player action text
- Current scene context
- Relevant state snapshot

**Output returned:**

- Route classification
- One or more recommended next nodes to invoke

**Responsibilities:**

- Classify the turn as dialogue, exploration, combat, inventory, lore query, quest progression, or mixed action
- Support conditional routing based on both action type and scene context
- Make route recommendations explicit and auditable
- Support the Supervisor, which remains the final authority for execution control

### World / Lore Agent

**Type:** LLM-backed specialist agent

**Purpose:**  
Provide grounded world knowledge and maintain setting consistency.

**Input received:**

- Current location and environment
- Relevant lore data
- Quest context
- NPC context
- Relevant state snapshot
- Player action when relevant to exploration or world interaction

**Output returned:**

- Structured world facts relevant to the turn
- Environmental details
- Proposed lore-consistent consequences

**Responsibilities:**

- Keep the setting internally consistent
- Ground responses in known locations, factions, items, rumors, and history
- Propose outcomes, but never directly modify canonical state

### NPC Agent

**Type:** LLM-backed specialist agent

**Purpose:**  
Generate NPC dialogue, reactions, motives, and social behavior.

**Input received:**

- NPC profiles
- Relationship state
- Scene context
- Relevant state snapshot
- Player dialogue or action

**Output returned:**

- NPC speech or reaction
- Emotional stance, intent, or behavioral shift
- Proposed social consequences

**Responsibilities:**

- Keep named characters distinct and believable
- Reflect goals, personality, and memory of prior interactions
- Suggest outcomes without committing state changes directly

### Quest Agent

**Type:** LLM-backed specialist agent

**Purpose:**  
Interpret quest progression, branching, and consequences.

**Input received:**

- Active quest data
- Completed events
- Relevant player choices
- World and NPC context
- Relevant state snapshot

**Output returned:**

- Proposed quest progress interpretation
- Objective status markers
- New branches, hooks, or reward proposals

**Responsibilities:**

- Track whether the player advanced, delayed, failed, or altered a quest
- Introduce meaningful consequences for major decisions
- Support branching progression without breaking continuity

### Rules / Resolution Agent

**Type:** LLM-backed specialist agent, optionally combined with deterministic helper logic

**Purpose:**  
Resolve uncertain or contested actions using the project’s simplified RPG mechanics.

**Input received:**

- Player attempted action
- Relevant stats, tags, or inventory
- Difficulty information
- Combat or skill-check rules
- Relevant state snapshot

**Output returned:**

- Roll request or resolved roll result
- Success, failure, or partial-success outcome
- Proposed mechanical consequence

**Responsibilities:**

- Apply the simplified rules consistently
- Resolve combat, skill checks, and contested actions
- Return structured results for downstream validation and state update

### Continuity / Critic Agent

**Type:** LLM-backed specialist agent

**Purpose:**  
Validate proposed outcomes before they are committed to canonical state.

**Input received:**

- Proposed outputs from specialist agents
- Relevant state snapshot
- Recent event log
- Proposed state update bundle

**Output returned:**

- Approval, rejection, or warning
- Conflict notes
- Suggested corrections

**Responsibilities:**

- Detect contradictions with prior state
- Detect impossible actions or illegal transitions
- Detect missing dependencies, broken quest flow, or impossible NPC knowledge
- Ensure the turn result is coherent before state mutation occurs

**Acceptance criteria checked by the Critic:**

- No contradiction with canonical prior state
- No invalid quest or combat transition
- No state mutation without a causal event
- No NPC reaction based on unavailable knowledge
- No final outcome missing a player-visible consequence

### State Updater

**Type:** Deterministic Python component

**Purpose:**  
The only component authorized to commit changes to canonical game state.

**Input received:**

- Approved update proposal
- Current canonical state
- Event log for the turn

**Output returned:**

- New canonical state
- Turn delta / audit record
- Updated event history entry

**Responsibilities:**

- Commit approved changes only
- Keep every state transition explicit and traceable
- Record what changed, why it changed, and which node proposed it

### Narrator / Response Agent

**Type:** LLM-backed specialist agent

**Purpose:**  
Convert approved turn outcomes into immersive player-facing text.

**Input received:**

- Approved turn result
- Relevant state snapshot
- Scene context
- NPC dialogue or action outcomes

**Output returned:**

- Final narrative response for the player
- Optional next-scene framing or choice prompt

**Responsibilities:**

- Present a clean, immersive, player-visible response
- Hide internal system mechanics and node handoffs
- Set up the next turn naturally

## Canonical state authority

Canonical game state is stored externally and persists across turns through a shared state object rather than relying on prompt memory alone. This supports long-running sessions, repeatable execution, and auditable state transitions. Only the State Updater is allowed to modify canonical game state. All other nodes may receive only the relevant subset of state for their task and may propose changes, but they cannot commit those changes directly. :contentReference[oaicite:5]{index=5}

The formal mutation pattern is:

`specialist node proposes -> critic validates -> state updater commits -> narrator renders` :contentReference[oaicite:6]{index=6}

This ensures that world facts, quest progress, combat status, inventory, and NPC memory remain controlled and traceable across turns. :contentReference[oaicite:7]{index=7}

## State structure

To keep orchestration clean, the system should distinguish between canonical game state, transient turn state, and session / execution metadata. :contentReference[oaicite:8]{index=8}

**Canonical game state** includes persistent information needed across turns, such as:

- `current_scene`
- `location`
- `active_quests`
- `npc_states`
- `inventory`
- `party_status`
- `recent_events`

**Transient turn state** includes execution-specific information for the current turn, such as:

- `player_action`
- `selected_route`
- `specialist_outputs`
- `proposed_updates`
- `validation_status`
- `current_turn_events`
- `final_response`

**Session / execution metadata** includes system-level information used to track and manage execution, such as:

- `turn_id`
- `session_id`
- `timestamp`
- `retry_count`

The canonical game state acts as the long-lived source of truth for the game world, transient turn state supports routing, validation, and response generation during the current turn, and session / execution metadata supports traceability, retry behavior, and orchestration control. Separating these layers makes the system easier to reason about and better aligned with stateful workflow patterns, where domain state and execution metadata are often tracked separately for observability and recovery. :contentReference[oaicite:9]{index=9}

## Routing logic

The Supervisor manages the turn lifecycle, while the Router classifies the player action and recommends the next execution path. The Router may recommend one or more specialist nodes in sequence, but the Supervisor remains the final authority for node execution, retries, fallback behavior, and safe turn termination. :contentReference[oaicite:10]{index=10}

**Example routing policy:**

- If the player asks about the environment or explores a location, route to the World / Lore Agent
- If the player speaks to, persuades, threatens, or provokes a character, route to the NPC Agent
- If the player attempts something risky, uncertain, or contested, route to the Rules / Resolution Agent
- If the action affects a quest objective or branch, route to the Quest Agent
- If multiple specialist proposals must be reconciled, route to the Continuity / Critic Agent
- After validation, route to the State Updater
- At the end of the turn, route to the Narrator / Response Agent :contentReference[oaicite:11]{index=11}

Some turns may invoke multiple specialist nodes in sequence before validation and state commit. For example, a player threatening an NPC during an active quest may require NPC interpretation, rules resolution, quest impact analysis, critic validation, state update, and final narration. :contentReference[oaicite:12]{index=12}

## Failure handling and retry behavior

The turn loop should support controlled failure handling. If validation fails, the system may:

- Request a corrected proposal from the responsible specialist node
- Fall back to a safer alternate route
- Terminate the turn with a graceful recovery message :contentReference[oaicite:13]{index=13}

Retries should be bounded by policy to prevent infinite repair loops and preserve predictable turn execution. For example, the orchestrator may allow up to `3` retries for a turn, tracked through `retry_count` in session / execution metadata. Once that limit is reached, the Supervisor should abort the turn safely rather than allowing an invalid state mutation or an unbounded retry cycle.

If no valid route is found or repeated validation failures occur, the Supervisor should abort the turn safely rather than allowing an invalid state mutation. :contentReference[oaicite:14]{index=14}

## Loop termination

### Turn completion

A turn ends when:

- The current player action has been fully resolved
- Any required state updates have been validated and committed
- A final player-facing response has been generated :contentReference[oaicite:15]{index=15}

### Session completion

A session ends when one of the following occurs:

- The starting quest is completed
- The starting quest fails permanently
- The player chooses to quit
- The party is defeated or reaches a terminal game-over state
- A predefined demo or session turn limit is reached :contentReference[oaicite:16]{index=16}

## Summary of intent

This architecture is designed to make the system controlled, inspectable, and implementation-friendly. It treats orchestration as a deterministic stateful workflow, uses specialist agents for bounded cognitive tasks, and protects canonical game state through explicit validation and single-writer authority. :contentReference[oaicite:17]{index=17}
