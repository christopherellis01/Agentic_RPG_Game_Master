# Rules Agent – Agnes

## Overview

This component resolves player actions into structured outcomes within the RPG system. It ensures consistent and reliable behavior across combat, dialogue, and exploration interactions. The module produces structured outputs that integrate with the orchestration layer.


## Features

* Action classification: combat, dialogue, exploration, unknown
* State-aware combat resolution (enemy HP updates)
* Structured outputs for integration
* Error handling for invalid or empty input
* Demo examples showing success and failure cases
* Fully tested using pytest
* Documentation generated using pdoc


## Project Structure

rules_agent_module/
├── src/
│   └── agents/
│       └── rules_agent.py
├── tests/
│   └── test_rules_agent.py
├── demo/
│   └── example_usage.py
├── pytest.ini
├── README_rules_agent.md
├── pytest_output.png
├── pdoc_webpage.png
├── python_example_usage_py.png


## Core Function

```python
resolve_action(player_action: str, state: Dict) -> Dict
```

Returns:

* action_type
* outcome
* reason
* consequence


## Testing

* Implemented using pytest
* Covers classification, edge cases, and state logic
* All tests pass successfully


## Examples

### Example 1: Successful Attack

Input:
resolve_action("attack goblin", {"enemy_hp": 20})

Output:
{
"action_type": "combat",
"outcome": "success",
"reason": "Roll = 9",
"consequence": {
"enemy_hp_change": -10,
"new_enemy_hp": 10
}
}


### Example 2: Failed Attack

Input:
resolve_action("attack goblin", {"enemy_hp": 20})

Output:
{
"action_type": "combat",
"outcome": "failure",
"reason": "Roll = 3",
"consequence": {
"enemy_hp_change": 0,
"new_enemy_hp": 20
}
}


## Demo File

File:
demo/example_usage.py

This script:

* runs the rules agent
* guarantees one success and one failure
* prints both outputs


## Execution Steps (Command Prompt)

### 1. Go to project folder

```bash
cd /d "C:\Users\agnes\OneDrive\Documents\UCF SPRING 2026 classes\CAP 6640_NLP_Computer Understanding of Natural Language\Agentic_RPG_Game_Master"
```

### 2. Set Python path

```bash
set PYTHONPATH=.
```

### 3. Run tests

```bash
python -m pytest tests\test_rules_agent.py
```

### 4. Generate documentation

```bash
python -m pdoc src.agents.rules_agent
```

Open in browser:
http://localhost:8080


### 5. Run demo example

```bash
python demo\example_usage.py
```


## Output Screenshots

* pytest_output.png → shows passing tests
* pdoc_webpage.png → shows generated documentation
* python_example_usage_py.png → shows success + failure output


## Role in Project

This module ensures reliable rule resolution before orchestration.
Responsibilities included:

* rules logic implementation
* state handling (enemy HP updates)
* testing and validation
* documentation and demo


## Summary

The Rules Agent module classifies player actions and returns structured outcomes. It supports combat, dialogue, and exploration while maintaining state consistency. The module is fully tested, documented, and ready for integration into the RPG system.
