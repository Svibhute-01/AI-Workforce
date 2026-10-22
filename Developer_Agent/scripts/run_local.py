from app.graph.builder import build_developer_graph

graph = build_developer_graph()

final_state = graph.invoke({
    "task": "Create a user registration API endpoint",
    "tech_stack": "Python, FastAPI",
    "output": None,
    "validation_errors": [],
    "retries": 0,
    "project_id": "demo_run",
})

output = final_state["output"]

print()
print("ATTEMPTS:", final_state["retries"])
print("ERRORS LEFT:", final_state["validation_errors"])
print("SUMMARY:", output.summary)
for change in output.changes:
    print(" -", change.action, change.path)