# KNOWLEDGE LAYER NOTE

## Overview

The knowledge layer connects the project’s structured seed data to the live agent workflow. It is responsible for taking canonical runtime state from `GameState`, enriching it with authored data from `data/`, and packaging that information into the input models expected by the Lore, NPC, and Quest agents.

The goal is to keep world facts, NPC profiles, quest details, and scene context outside of free-form prompts while still giving each specialist agent the information it needs to respond coherently.

At a high level, the knowledge flow is:

`canonical GameState -> retrieval helpers -> seed JSON enrichment -> specialist agent input model`

---

## Design principle

The knowledge layer follows a split-source model:

- Canonical `GameState` is the source of truth for live, mutable session data.
- Seed JSON files are the source of truth for authored, mostly static content.
- Retrieval functions combine both sources into narrow, structured agent inputs.

This keeps persistent state controlled while still preserving richer authoring detail such as NPC personalities, location facts, relationship summaries, and quest context.

---

## Current data sources

### `data/world/world_state.json`

Stores world and location information.

Currently used for:

- world summary
- location lookup
- location descriptions
- relevant location facts
- setting context for Lore Agent prompts

The retrieval layer supports lookup by either location id or display name because the current world data may represent locations in both forms.

### `data/npcs/npc_data.json`

Stores authored NPC profiles.

Currently used for:

- NPC id
- name
- location
- role
- personality traits
- goals
- disposition
- knowledge
- relationship summary

This file provides the richer character data that the runtime `NPCState` model does not yet fully preserve.

### `data/quests/quest_data.json`

Stores authored quest data.

Currently used for:

- quest id
- quest name
- objective structure
- seeded quest context

Live quest status comes from canonical state, while the seed file remains the authoring source for static quest definitions.

### Canonical `GameState`

Defined in `src/models/state_models.py`.

Currently used for:

- current location
- current scene
- active quests and objective completion
- NPC live state
- recent events
- inventory
- combatants
- transient turn state

The knowledge layer treats this as the authoritative record of what has changed during play.

---

## Core file

### `src/retrieval.py`

**Type:** Deterministic Python support layer

**Purpose:**  
Bridge canonical runtime state and structured seed data.

**Input received:**

- Current `GameState`
- Optional lookup keys such as `npc_id` or `location_key`
- Seed JSON files from `data/`

**Output returned:**

- `LoreAgentInput`
- `NPCAgentInput`
- `QuestAgentInput`
- raw lookup results for locations, NPCs, and quests

**Responsibilities:**

- Load world, NPC, and quest seed data
- Cache seed JSON data during runtime
- Look up locations by id or display name
- Look up NPC profiles by id
- Look up quest definitions by id
- Build structured input objects for specialist agents
- Keep mutable session data grounded in canonical state
- Enrich agent inputs with authored details that are not yet modeled in runtime state

---

## Current helper functions

### JSON loaders

`_load_world_data()`, `_load_npc_data()`, and `_load_quest_data()` read the structured seed files from `data/`.

These functions cache their loaded JSON so the app does not reread the same files on every turn.

### Location lookup

`get_location_data(location_key)` returns location data from `world_state.json`.

It accepts either:

- a location id such as `oakshade_village`
- a display name such as `Oakshade Village`

This makes the layer tolerant of the current data shape.

### World summary lookup

`get_world_summary()` returns top-level world context from the world seed file.

The Lore Agent uses this as broad setting context when responding to exploration or lore actions.

### NPC lookup

`get_npc_data(npc_id)` returns an authored NPC profile from `npc_data.json`.

This is where personality traits, goals, role, knowledge, and relationship summary are retrieved.

### NPC location lookup

`get_npcs_at_location(state, location_key)` returns NPC ids whose live state places them at the current location.

This uses canonical state rather than only seed data, so it can support future NPC movement.

### Quest lookup

`get_quest_data(quest_id)` returns authored quest data from `quest_data.json`.

At the moment, live quest status is still pulled from canonical state.

---

## Agent input builders

### `build_lore_agent_input(state)`

Builds the structured input for the Lore Agent.

Uses:

- current player action
- current scene
- current location
- world summary
- location-specific facts
- active quest summaries

This lets the Lore Agent answer exploration and lore actions using grounded setting context instead of inventing facts from scratch.

### `build_npc_agent_input(state, npc_id)`

Builds the structured input for the NPC Agent.

Uses:

- current player action
- NPC live state
- authored NPC role
- authored personality traits
- NPC goals
- NPC disposition
- current scene
- relationship summary
- authored NPC knowledge

This is the main path that makes characters like Mara, Corvin, and Harlan behave differently.

### `build_quest_agent_input(state)`

Builds the structured input for the Quest Agent.

Uses:

- current player action
- current scene
- active quest summaries
- completed objectives
- recent player choices
- world context
- NPCs present at the current location

This gives the Quest Agent enough context to decide whether an action advances, delays, branches, or fails a quest.

---

## Current runtime flow

In the live FastAPI demo, the knowledge layer is used during `/turn`.

The flow is:

1. The API receives a player action.
2. The state manager starts a new turn and stores the player action.
3. The router classifies the action.
4. The API decides which specialist agents are needed.
5. For each needed agent, `src/retrieval.py` builds the correct input object.
6. The specialist agent runs with structured context.
7. If a live agent call times out, the API uses local fallback behavior built from the same seeded knowledge.
8. The response is returned to the demo UI.

This means the knowledge layer supports both live LLM agent calls and deterministic demo fallbacks.

---

## Why this matters

Without a knowledge layer, each agent would need to manually know where to find world, NPC, and quest data. That would spread data-access logic across the system and make prompts harder to control.

The current knowledge layer improves the project by:

- centralizing seed-data access
- keeping agent inputs structured
- reducing prompt clutter
- making NPC and quest context reusable
- preserving canonical state as the source of truth for live changes
- making the demo easier to debug
- giving future memory work a clear integration point

---

## Current limitations

The current knowledge layer is intentionally simple.

Known limitations:

- Seed data is stored in JSON rather than a database or vector index.
- JSON caches do not automatically reload unless the Python process restarts.
- NPC memory is currently seeded from authored `knowledge`, not accumulated interaction memory.
- Relationship changes are proposed but not yet deeply persisted.
- Quest lookup exists, but quest progression still relies mostly on canonical state summaries.
- Retrieval is exact/id-based, not semantic search.
- The layer does not yet rank relevant facts by action intent.

---

## Suggested next steps

- Add tests directly for `src/retrieval.py`.
- Add a cache reset helper for development.
- Expand runtime state models to preserve richer NPC and location fields.
- Track accumulated NPC memory across turns.
- Store relationship changes as structured state.
- Add relevance filtering so agents receive only the most useful facts.
- Consider a lightweight semantic retrieval layer if the world data grows beyond small JSON files.
- Add explicit knowledge citations in agent outputs for debugging.

---

## Summary

The knowledge layer is the project’s bridge between structured game content and live agent execution. It reads canonical state for what is true right now, enriches that state with authored JSON data, and returns typed input objects for Lore, NPC, and Quest agents.

This gives the system grounded context without letting agents freely invent or mutate world knowledge. It is currently simple, testable, and JSON-based, but it provides the foundation for richer memory, retrieval, and continuity in future iterations.
