import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from chatgraph import graph
from config.settings import DEFAULT_MODEL
from memory.episodic import init_db, save_episode   # ← add
from worker.background import tick                   # ← add

init_db()  # ← add (creates SQLite table on first run)

st.set_page_config(page_title="Ollama Chat", page_icon="🦙", layout="centered")
st.title("🦙 Ollama Chatbot")
st.caption(f"Powered by LangGraph · Model: `{DEFAULT_MODEL}`")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("⚙️ Settings")
    model = st.text_input("Ollama model", value=DEFAULT_MODEL)
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

if user_input := st.chat_input("Ask me anything…"):
    st.session_state.messages.append(("user", user_input))
    save_episode("user", user_input)        # ← add

    with st.chat_message("user"):
        st.markdown(user_input)

    lc_messages = [
        HumanMessage(content=c) if r == "user" else AIMessage(content=c)
        for r, c in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        for chunk in graph.stream(
            {"messages": lc_messages},
            config={"configurable": {"model": model}},
            stream_mode="messages",
        ):
            message_chunk, _ = chunk
            if hasattr(message_chunk, "content"):
                full_response += message_chunk.content
                placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)

    st.session_state.messages.append(("assistant", full_response))
    save_episode("assistant", full_response)   # ← add
    tick(role="user")                          # ← add (triggers extraction every 3 turns)


# import streamlit as st
# from langchain_core.messages import HumanMessage, AIMessage
# from chatgraph import graph
# from config.settings import DEFAULT_MODEL

# st.set_page_config(page_title="Ollama Chat", page_icon="🦙", layout="centered")
# st.title("🦙 Ollama Chatbot")
# st.caption(f"Powered by LangGraph · Model: `{DEFAULT_MODEL}`")

# if "messages" not in st.session_state:
#     st.session_state.messages = []

# with st.sidebar:
#     st.header("⚙️ Settings")
#     model = st.text_input("Ollama model", value=DEFAULT_MODEL)
#     if st.button("🗑️ Clear conversation"):
#         st.session_state.messages = []
#         st.rerun()
#     st.markdown("---")
#     st.markdown("**Pull a model:**")
#     st.code("ollama pull llama3.2", language="bash")

# for role, content in st.session_state.messages:
#     with st.chat_message(role):
#         st.markdown(content)

# if user_input := st.chat_input("Ask me anything…"):
#     st.session_state.messages.append(("user", user_input))
#     with st.chat_message("user"):
#         st.markdown(user_input)

#     lc_messages = []
#     for role, content in st.session_state.messages:
#         if role == "user":
#             lc_messages.append(HumanMessage(content=content))
#         else:
#             lc_messages.append(AIMessage(content=content))

#     with st.chat_message("assistant"):
#         placeholder = st.empty()
#         full_response = ""

#         for chunk in graph.stream(
#             {"messages": lc_messages},
#             config={"configurable": {"model": model}},
#             stream_mode="messages",
#         ):
#             message_chunk, _ = chunk
#             if hasattr(message_chunk, "content"):
#                 full_response += message_chunk.content
#                 placeholder.markdown(full_response + "▌")

#         placeholder.markdown(full_response)

#     st.session_state.messages.append(("assistant", full_response))