from src.agents.rules_agent import resolve_action

print("=== Example 1: Successful Attack ===")

success_result = resolve_action("attack goblin", {"enemy_hp": 20})
while success_result["outcome"] != "success":
    success_result = resolve_action("attack goblin", {"enemy_hp": 20})

print(success_result)


print("\n=== Example 2: Failed Attack ===")

failure_result = resolve_action("attack goblin", {"enemy_hp": 20})
while failure_result["outcome"] != "failure":
    failure_result = resolve_action("attack goblin", {"enemy_hp": 20})

print(failure_result)