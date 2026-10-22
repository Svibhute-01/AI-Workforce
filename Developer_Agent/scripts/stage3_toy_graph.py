from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class ToyState(TypedDict):
    task: str
    steps_done: list[str]


def step_one(state: ToyState) -> dict:
    print("Running step_one, task is:", state["task"])
    return {"steps_done": state["steps_done"] + ["step_one"]}


def step_two(state: ToyState) -> dict:
    print("Running step_two, so far:", state["steps_done"])
    return {"steps_done": state["steps_done"] + ["step_two"]}


# NEW: the third function
def step_three(state: ToyState) -> dict:
    print("Running step_three, so far:", state["steps_done"])
    return {"steps_done": state["steps_done"] + ["step_three"]}


builder = StateGraph(ToyState)

builder.add_node("step_one", step_one)
builder.add_node("step_two", step_two)
builder.add_node("step_three", step_three)          # NEW: register it

builder.add_edge(START, "step_one")
builder.add_edge("step_one", "step_two")
builder.add_edge("step_two", "step_three")          # CHANGED: was ("step_two", END)
builder.add_edge("step_three", END)                 # NEW: step_three now ends the graph

graph = builder.compile()

final_state = graph.invoke({"task": "build login", "steps_done": []})

print("FINAL STATE:", final_state)