from app.schemas.developer import FileChange
from app.tools.workspace import Workspace, WorkspaceError

ws = Workspace("demo_project")
print("Workspace root:", ws.root)

# 1. Normal write
changes = [
    FileChange(path="app/main.py", action="create",
               content="print('hello')\n", explanation="entry point"),
    FileChange(path="requirements.txt", action="create",
               content="fastapi\n", explanation="deps"),
]
print("Written:", ws.apply_changes(changes))
print("Files:  ", ws.list_files())
print("Read back:", repr(ws.read_file("app/main.py")))

# 2. Attack attempts: every one of these must be refused
bad_paths = [
    "../escape.txt",
    "../../escape.txt",
    "C:/Windows/escape.txt",
    "app/../../escape.txt",
]
print()
for p in bad_paths:
    try:
        ws.write_file(p, "should never be written")
        print("DANGER, was allowed:", p)
    except WorkspaceError as e:
        print("Blocked:", p)