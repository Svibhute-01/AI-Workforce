from app.schemas.developer import DeveloperOutput, FileChange
import app.graph.nodes as nodes
from app.graph.builder import build_developer_graph


class FakeChain:
    """Pretends to be the developer chain. No Gemini, no quota."""

    def __init__(self):
        self.calls = 0

    def invoke(self, inputs: dict) -> DeveloperOutput:
        self.calls += 1
        print(f"   [fake] call #{self.calls}, feedback seen: {bool(inputs['feedback'])}")

        if self.calls == 1:
            # First attempt: broken code (missing colon)
            code = "def add(a, b)\n    return a + b\n"
        else:
            # Later attempts: fixed code
            code = "def add(a, b):\n    return a + b\n"

        return DeveloperOutput(
            summary=f"fake attempt {self.calls}",
            changes=[
                FileChange(
                    path="app/math_utils.py",
                    action="create",
                    content=code,
                    explanation="fake file",
                )
            ],
        )


# Replace the real chain with the fake one
nodes.developer_chain = FakeChain()

graph = build_developer_graph()

final_state = graph.invoke({
    "task": "anything",
    "tech_stack": "Python",
    "output": None,
    "validation_errors": [],
    "retries": 0,
})

print()
print("ATTEMPTS:   ", final_state["retries"])
print("ERRORS LEFT:", final_state["validation_errors"])
print("SUMMARY:    ", final_state["output"].summary)