import sys
from app.schemas.developer import DeveloperOutput, FileChange
import app.graph.nodes as nodes
from app.graph.builder import build_developer_graph

# Usage:
#   python -m scripts.stage5_fake_run_test          -> normal run (fails once, then succeeds)
#   python -m scripts.stage5_fake_run_test cap      -> always fails (tests the retry cap)
ALWAYS_FAIL = len(sys.argv) > 1 and sys.argv[1] == "cap"


def fc(path, content):
    return FileChange(path=path, action="create", content=content, explanation="fake")


class FakeChain:
    def __init__(self):
        self.calls = 0

    def invoke(self, inputs: dict) -> DeveloperOutput:
        self.calls += 1
        print(f"   [fake] call #{self.calls}, feedback seen: {bool(inputs['feedback'])}")

        if ALWAYS_FAIL or self.calls == 1:
            # Valid syntax, but the test fails (1 + 1 is not 3)
            test_code = "def test_add():\n    assert 1 + 1 == 3\n"
        else:
            test_code = "def test_add():\n    assert 1 + 1 == 2\n"

        return DeveloperOutput(
            summary=f"fake attempt {self.calls}",
            changes=[
                fc("requirements.txt", "pytest\n"),
                fc("app/__init__.py", ""),
                fc("app/main.py", "VALUE = 1\n"),
                fc("tests/test_math.py", test_code),
            ],
        )


# Replace the real chain with the fake one
nodes.developer_chain = FakeChain()

graph = build_developer_graph()

final_state = graph.invoke({
    "project_id": "fake_run_project",
    "task": "anything",
    "tech_stack": "Python",
    "output": None,
    "validation_errors": [],
    "retries": 0,
    "status": "running",
})

print()
print("ATTEMPTS:   ", final_state["retries"])
print("STATUS:     ", final_state["status"])
print("ERRORS LEFT:", bool(final_state["validation_errors"]))