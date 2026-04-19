# CURRENT ORCHESTRATION FLOW

## Purpose of this document

This document explains what is currently implemented in the orchestration and app-flow layer of the project. The main architecture document describes the intended full system design, but this file is meant to show what is already working now and how the current pieces fit together.

At this stage, the system does not yet execute full specialist-agent logic. Instead, it uses a deterministic orchestration flow with placeholder node execution so the routing, sequencing, retry behavior, and shared-state transitions can be tested end to end.

---

## What is currently implemented

The current implementation includes the following orchestration-related pieces:

- structured game state models using Pydantic
- JSON-based seed data loading through the state manager
- initial game-state construction
- per-turn state reset through `start_new_turn()`
- deterministic route classification in `router.py`
- execution-plan generation in `orchestrator.py`
- placeholder node execution for planned nodes
- bounded retry and fallback behavior
- per-turn event logging for traceability and debugging

This means the project can already simulate the full control flow of a turn, even though the specialist node logic is still represented by placeholders.

---

## Current file responsibilities

### `src/models/state_models.py`
Defines the structured state used across the workflow.

This includes:
- canonical game state
- transient turn state
- session / execution metadata
- supporting state objects such as quests, NPCs, party status, and event records

These models act as the shared state contract for the application.

### `src/state_manager.py`
Handles loading, building, resetting, saving, and reloading state.

Current responsibilities include:
- loading seed JSON files from `data/`
- building the initial canonical state
- creating transient turn state
- creating session metadata
- building the initial `GameState`
- resetting the transient turn state for each new turn
- saving and loading full state snapshots as JSON

### `src/router.py`
Classifies player actions into execution routes.

The current router is deterministic and keyword-based. It maps a player action to a route such as:
- `dialogue`
- `exploration`
- `combat`
- `quest_progression`
- `lore_query`
- `mixed_action`

It also returns the recommended next nodes for that route.

### `src/orchestrator.py`
Controls the main application flow for a single turn.

The orchestrator currently:
1. starts a new turn
2. calls the router
3. stores the selected route in transient state
4. builds an execution plan
5. executes the planned nodes using placeholder behavior
6. applies bounded retry and fallback behavior if a node fails
7. records orchestration events for debugging and auditability
8. returns a structured `OrchestrationResult`

---

## Current turn lifecycle

At the moment, a single turn works like this:

`player action -> start new turn -> classify route -> build execution plan -> execute placeholder nodes -> record events -> return orchestration result`

In more detail:

### 1. Initial state is created
The system begins by loading the structured seed data from JSON files and constructing a fresh `GameState`.

This includes:
- canonical world/game state
- fresh transient turn state
- session metadata such as `session_id`, `turn_id`, and `retry_count`

### 2. A new turn starts
When `run_turn()` is called, the orchestrator resets the transient turn state using `start_new_turn()`.

This:
- increments the turn counter
- resets retry tracking
- updates the timestamp
- stores the current player action

### 3. The router classifies the player action
The orchestrator sends the player action and current state to the router.

The router returns a `RouteDecision` containing:
- the route label
- the next nodes to invoke
- the reason for the decision

For example:
- asking an NPC about a quest may become `mixed_action`
- searching a ruin may become `exploration`
- attacking an enemy may become `combat`

### 4. The orchestrator stores the route
The selected route is written into transient turn state.

This allows the turn state to reflect the actual control decision that was made for the current input.

### 5. The execution plan is built
The orchestrator converts the route decision into an ordered execution plan.

Right now, this simply mirrors the router’s recommended node sequence. Later, this could become more sophisticated and enforce additional sequencing rules.

### 6. Planned nodes are executed with placeholder behavior
The orchestrator walks through the planned node list and simulates execution.

At this stage, the nodes do not yet call real specialist-agent implementations. Instead, they return placeholder execution results so the flow can be tested without depending on the unfinished parts of the project.

This makes it possible to validate:
- route selection
- execution order
- turn-event logging
- retry and abort behavior

### 7. Retry and fallback behavior are applied
If a node is marked as failed during testing, the orchestrator:
- increments `retry_count`
- retries the node until `max_retries` is reached
- aborts execution safely if retries are exhausted

This is intentionally bounded so the turn loop cannot retry forever.

### 8. Events are recorded
The orchestrator logs important control-flow events into `current_turn_events`.

Examples include:
- route selected
- route reason
- execution plan built
- node executed
- node retry
- execution aborted

These events make the flow easier to inspect in notebooks and help explain what happened during a turn.

### 9. A structured orchestration result is returned
The result of the turn is returned as an `OrchestrationResult`.

This includes:
- the player action
- the selected route
- the next nodes
- the execution plan
- the placeholder execution results
- whether the turn aborted
- the updated shared state

---

## What the current implementation proves

Even without real specialist-agent execution, the current system already proves that the core app flow works.

Specifically, it shows that the project can:
- initialize structured state
- accept a player action
- classify the action into a route
- build an ordered plan
- simulate node execution
- handle retry / fallback conditions
- log control-flow events
- return an updated state object

That is an important milestone because it means the project now has a functioning orchestration skeleton rather than just a static architecture idea.

---

## What is still placeholder behavior

The following areas are still placeholders or intentionally simplified:

- specialist node execution
- real lore retrieval
- real NPC response generation
- real quest interpretation
- real rules/combat resolution
- critic-based validation before state mutation
- final narrator-generated player-facing output

Those pieces can later be plugged into the existing orchestration flow by replacing placeholder node execution with real module calls.

---

## Why this matters

This current implementation gives the project a stable control layer before the rest of the team’s work is fully integrated.

That matters because:
- the routing behavior can already be tested
- the shared-state lifecycle is already defined
- turn execution is already inspectable
- teammates have a clear orchestration path to plug their modules into later

In other words, the project now has a working backbone.

---

## Summary

Right now, the project has a functioning orchestration skeleton built around structured state, deterministic routing, planned node sequencing, bounded retry behavior, and turn-event logging. The specialist nodes are still placeholders, but the application flow itself is already working end to end.

That makes the current implementation a strong foundation for integrating memory/state/lore retrieval, rules logic, evaluation, and the remaining specialist components in the next phase of the project.

---

## Suggested next steps for the remaining team roles

Now that the orchestration skeleton is in place, the biggest priority for the rest of the team is plugging real functionality into the flow that already exists.

For **Mazin**, I would focus on making the system actually *know things* in a useful way. That means figuring out how world lore, NPC information, quest context, and persistent memory should be stored and retrieved so the right node gets the right context at the right time. I would keep that work practical and structured: define what information needs to be accessible, how it should be looked up, and what format it should come back in so it can plug into the orchestrator cleanly instead of creating extra confusion. I've used the API structure from our PydanticAI to give you a starting `lore_agent` and `npc_agent`.

For **Agnes**, I would focus on making the system actually *behave correctly* once real node logic starts replacing the placeholders. That means implementing the simplified rules logic, thinking through how success/failure should be resolved, and building the evaluation/testing side so we can tell whether the system is doing what we expect. I would especially focus on tests around rule resolution, state transitions, retry behavior, and whether the outputs make sense for the type of turn being processed. Agin, I've got a start for your section, mainly rules resolution, evaluation and testing. 

*Mazin*, your focus is to help the system become more informed. *Agnes*, you will help the system become more reliable. My orchestration layer is now in a good place to support both of those efforts.