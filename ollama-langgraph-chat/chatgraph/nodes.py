from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from chatgraph.state import ChatState
from config.settings import DEFAULT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT
from memory.retriever import build_memory_context


def get_llm(model: str = DEFAULT_MODEL) -> ChatOllama:
    return ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        temperature=0.7,
        streaming=True,
    )


def chat_node(state: ChatState, config: RunnableConfig | None = None) -> dict:
    model = DEFAULT_MODEL
    if config:
        model = config.get("configurable", {}).get("model", DEFAULT_MODEL)

    # Get the latest user message for context-aware retrieval
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break

    # Build memory context from KG relevant to current message
    memory_context = build_memory_context(last_user_message)

    # Inject into system prompt only if memory exists
    full_system = SYSTEM_PROMPT
    if memory_context:
        full_system += f"\n\n{memory_context}\n\nUse this context naturally in your responses without explicitly announcing it."

    llm = get_llm(model)
    messages = [SystemMessage(content=full_system)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}