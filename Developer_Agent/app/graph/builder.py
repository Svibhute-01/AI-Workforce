from langgraph.graph import StateGraph, START, END
from app.graph.states import DeveloperState
from app.graph.nodes import generate_node, validate_node, give_up_node
from app.graph.routing import route_after_validate


def build_developer_graph():
    builder = StateGraph(DeveloperState)

    builder.add_node("generate", generate_node)
    builder.add_node("validate", validate_node)
    builder.add_node("give_up", give_up_node)

    builder.add_edge(START, "generate")
    builder.add_edge("generate", "validate")
    builder.add_conditional_edges("validate", route_after_validate)
    builder.add_edge("give_up", END)

    return builder.compile()