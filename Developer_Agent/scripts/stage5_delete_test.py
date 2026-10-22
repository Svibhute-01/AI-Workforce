from app.schemas.developer import FileChange
from app.tools.workspace import Workspace, WorkspaceError

ws = Workspace("delete_test")

ws.apply_changes([
    FileChange(path="app/routers/auth.py", action="create", content="x = 1\n", explanation="old"),
    FileChange(path="app/routes/auth.py", action="create", content="x = 2\n", explanation="new"),
])
print("Before:", ws.list_files())

print(ws.apply_changes([
    FileChange(path="app/routers/auth.py", action="delete", content="", explanation="obsolete"),
]))
print("After: ", ws.list_files())

# Deleting a missing file must not crash
print("Missing file deleted?", ws.delete_file("nope.py"))

# Protected and escaping paths must be refused
for p in [".venv/x.py", "../escape.txt"]:
    try:
        ws.delete_file(p)
        print("DANGER, was allowed:", p)
    except WorkspaceError:
        print("Blocked:", p)