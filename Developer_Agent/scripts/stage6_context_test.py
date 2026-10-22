from app.schemas.developer import FileChange
from app.tools.workspace import Workspace
from app.tools.context import build_existing_files_context

ws = Workspace("context_test")
print("Empty project:", repr(build_existing_files_context(ws)))

ws.apply_changes([
    FileChange(path="app/main.py", action="create", content="print('hi')\n", explanation="x"),
    FileChange(path="app/db.py", action="create", content="DB = 1\n", explanation="x"),
    FileChange(path="logo.png", action="create", content="binary-ish", explanation="x"),
])

print()
print(build_existing_files_context(ws))