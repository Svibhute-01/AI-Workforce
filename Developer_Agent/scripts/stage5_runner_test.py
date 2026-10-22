from app.tools.workspace import Workspace
from app.tools.runner import LocalRunner

ws = Workspace("demo_project")
runner = LocalRunner(ws.root)

# Give the demo project a tiny valid app
ws.write_file("requirements.txt", "pytest\n")
ws.write_file("app/__init__.py", "")
ws.write_file("app/main.py", "print('hello from main')\n")
ws.write_file("tests/test_math.py", "def test_add():\n    assert 1 + 1 == 2\n")

for step in ["create_venv", "install", "check_imports", "test"]:
    print(f"--- {step} ---")
    result = runner.run(step)
    print("ok:", result.ok, "| exit code:", result.exit_code)
    print(result.summary(500))
    print()

# The allowlist must refuse anything else
try:
    runner.run("rm -rf /")
except ValueError as e:
    print("Blocked:", e)