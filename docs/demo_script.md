# Demo Script — Agentic RPG Game Master

## Start the server

```bash
source ~/projects/school-notebooks/cap6640-NLP/GroupProject/rpg_venv/bin/activate
python -m uvicorn src.api:app --reload --port 8000

Open:

```
http://127.0.0.1:8000/
```

Demo path:

1. Click `Begin Anew` to reset the game state
2. Click `Draw your sword and attack the goblin"
3.Point out the agent flow:
- Router selects combat
- Rules Agent resolves the action
- State Updater applies HP changes when damage is dealt
- Narrator creates player-facing output
4. Show the Goblin HP persistence by attacking again.
5. Optional: try one NPC/lore action to show live LLM-backed specialists.
 
