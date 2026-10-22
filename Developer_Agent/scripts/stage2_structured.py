from app.chains.developer_chain import build_developer_chain

print("SCRIPT STARTED")

chain = build_developer_chain()

result = chain.invoke({
    "task": "Create a user registration API endpoint",
    "tech_stack": "Python, FastAPI",
})

print("TYPE:   ", type(result))
print("SUMMARY:", result.summary)
print()

for change in result.changes:
    print("PATH:   ", change.path)
    print("ACTION: ", change.action)
    print("WHY:    ", change.explanation)
    print("--- content ---")
    print(change.content)
    print("=" * 50)