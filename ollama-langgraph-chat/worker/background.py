import threading
from memory.episodic import get_unextracted, mark_extracted
from memory.extractor import extract_triples
from memory.neo4j_store import write_triples
from config.settings import EXTRACT_EVERY_N_TURNS

_turn_counter = 0
_lock = threading.Lock()


def tick(role: str = "user"):
    """Call this after every user message. Triggers extraction every N turns."""
    global _turn_counter
    if role != "user":
        return
    with _lock:
        _turn_counter += 1
        if _turn_counter >= EXTRACT_EVERY_N_TURNS:
            _turn_counter = 0
            thread = threading.Thread(target=_run_extraction, daemon=True)
            thread.start()


def _run_extraction():
    episodes = get_unextracted(limit=15)
    if not episodes:
        return
    print(f"[worker] Extracting triples from {len(episodes)} episodes...")
    triples = extract_triples(episodes)
    if triples:
        write_triples(triples)
        print(f"[worker] Wrote {len(triples)} triples to Neo4j")
    mark_extracted([e["id"] for e in episodes])