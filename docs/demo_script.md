# Demo Script — Agentic RPG Game Master


## Purpose

This demo shows a lightweight multi-agent RPG system that routes a player action through specialized components instead of relying on one model to do everything.

The main working flow demonstrated here is:

```
Player action
→ Router
→ Rules Agent
→ State Updater
→ Narrator
→ Updated game state
```

## Start the server

```
source ~/projects/school-notebooks/cap6640-NLP/GroupProject/rpg_venv/bin/activate
python -m uvicorn src.api:app --reload --port 8000
```

Open:

```
http://127.0.0.1:8000/
```

---

## Demo path

### 1. Reset the game

Click:

```
↻ BEGIN ANEW
```

**What should be happening:**                                                                                                                                                                         
The demo resets the in-memory game session and reloads the initial canonical game state. The scene should return to Oakshade Village, the NPC roster should repopulate, the quest log should reset, and the Encounter panel should show the Goblin at full health.

**What should be visible:**  
- Location: Oakshade Village
- Encounter: Goblin — HP 15 / 15
- Quest: The Missing Scout — not_started

**Why this matters:**  
This establishes the starting state for the demo. The system is not only rendering static text; it is loading structured world, NPC, quest, party, and combatant state from the backend.

---

### 2. Run the first combat turn

Click:

```
Draw your sword and attack the goblin.
```

**What should be happening:**  
The player action is sent to the FastAPI backend as a /turn request. The Router classifies the action as combat, then the Rules Agent resolves the attack. If the attack deals damage, the State Updater applies a structured HP change to the Goblin’s canonical combatant state. The Narrator then creates the player-facing result shown in the dialogue area.

**What should be visible:**  

- The Agent Council should show activity similar to:
- Router → Rules → State Updater → Narrator
- The dialogue area should show the player action, the Rules Agent’s mechanical result, and the Narrator’s response.
- The Encounter panel should either stay the same after a miss or update after a hit:

- Goblin — HP 15 / 15   # if the attack misses
- Goblin — HP 10 / 15   # if the attack partially succeeds
- Goblin — HP 5 / 15    # if the attack succeeds cleanly

**Why this matters:**  
This demonstrates the core agentic loop. Each component has a bounded responsibility: routing, rules resolution, state mutation, and narration are handled separately instead of being blended into one free-form model response.

---

### 3. Show persistent state across turns

Click the attack button again:

```
Draw your sword and attack the goblin.
```

**What should be happening:**  
The second attack should begin from the Goblin’s current HP, not from the original starting value. The backend reads the Goblin’s HP from canonical game state and passes that value into the Rules Agent before resolving the next attack.

**What should be visible:**  
If the first attack reduced the Goblin to 10 HP, the next result should continue from 10:
- Before second attack: Goblin — HP 10 / 15
- After second attack:  Goblin — HP 5 / 15 or HP 0 / 15

If the first attack missed, the Goblin may still be at:

```
Goblin — HP 15 / 15
```

**Why this matters:**  
This proves the system is remembering consequences across turns. The demo is not simply generating isolated text responses; it is maintaining persistent combatant state and updating that state through the State Updater.

---

### 4. Show defeated-enemy handling

After the Goblin reaches 0 HP, click the attack button one more time:

```
Draw your sword and attack the goblin.
```

**What should be happening:**  
The backend checks canonical combatant state before rolling another attack. Since the Goblin is already at 0 HP, the Rules Agent flow does not roll damage again. Instead, the system returns a clean resolved message that the Goblin is already defeated.

**What should be visible:**  

- Rules Agent: The Goblin is already defeated.
- Narrator: The Goblin is already defeated.
- Encounter: Goblin — HP 0 / 15

**Why this matters:**  
This prevents inconsistent combat behavior, such as repeatedly attacking an enemy that has already been defeated. It also shows that the backend is using state to constrain future actions.

---

### 5. Live-Agent path

The other quick actions call the LLM-backed specialist agents, such as the NPC, Lore, and Quest agents.

Example actions:  

- Approach the bar and ask Mara what's been happening.
- Sit across from the hooded man in the corner.
- Step outside and speak with Harlan at the forge.

**What should be happening:**  
These actions route to interpretation-heavy specialist agents. For example, an NPC-directed action should call the NPC Agent, while an exploration-style action may call the Lore Agent. These agents produce structured outputs that the frontend renders as dialogue or environmental narration.

**What should be visible:**  

The Agent Council may show activity such as:  

- Router → NPC
- Router → Lore
- Router → Quest

The dialogue area should show character or narrator responses grounded in the seeded world data.  

**Why this matters:**  
This demonstrates the part of the system where LLM-backed agents add value: dialogue, world interpretation, and quest-related reasoning. These tasks are less deterministic than combat resolution and are better suited to specialist language-model agents.

**Important note:**  
Because these paths rely on live model calls, they may be affected by network, API, or model availability. If one fails, the demo should show a safe fallback message instead of crashing.

**Expected fallback behavior:**  

*System: That specialist agent could not complete its live response, so the demo safely skipped that step. The rest of the system is still running.*


