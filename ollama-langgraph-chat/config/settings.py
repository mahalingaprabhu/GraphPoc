# Ollama
DEFAULT_MODEL    = "llama3"
OLLAMA_BASE_URL  = "http://localhost:11434"

# Neo4j
NEO4J_URI        = "bolt://127.0.0.1:7687"
NEO4J_USER       = "neo4j"
NEO4J_PASSWORD   = "xxxxx"

# Memory behaviour
EXTRACT_EVERY_N_TURNS = 3
MAX_EPISODES_CONTEXT  = 5
NEO4J_HOP_DEPTH       = 2

SYSTEM_PROMPT = """You are a helpful, concise, and friendly AI assistant.
You have contextual knowledge about the user from past conversations.
Use it naturally to give personalised responses — never say 'based on your memory' or 'I know that you'.
Just respond as if you naturally know the context."""
