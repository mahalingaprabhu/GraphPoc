from langgraph.graph import StateGraph, END
from chatgraph.state import ChatState
from chatgraph.nodes import chat_node


def build_graph():
    builder = StateGraph(ChatState)
    builder.add_node("chat", chat_node)
    builder.set_entry_point("chat")
    builder.add_edge("chat", END)
    return builder.compile()


compiled_graph = build_graph()