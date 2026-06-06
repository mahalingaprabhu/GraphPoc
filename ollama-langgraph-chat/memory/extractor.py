import json
import re
import requests
from config.settings import DEFAULT_MODEL, OLLAMA_BASE_URL

EXTRACTION_PROMPT = """You are a knowledge graph extractor.
Extract factual triples from the conversation below.
Each triple = (subject, predicate, object).

Rules:
- Subject is always "User" or a named entity the user mentions
- Use short, consistent predicate names: INTERESTED_IN, USES, OWNS, WORKS_ON, KNOWS, VISITED, ASKED_ABOUT
- Object is a concise noun phrase
- Extract 1-5 triples maximum, only clear facts
- Return ONLY a JSON array, no explanation, no preamble, no markdown

Example output:
[
  {{"subject": "User", "predicate": "INTERESTED_IN", "object": "LangGraph"}},
  {{"subject": "User", "predicate": "USES", "object": "Neo4j"}},
  {{"subject": "LangGraph", "predicate": "PART_OF", "object": "AI"}}
]

Conversation:
{conversation}

JSON array of triples:"""


def _extract_json_array(raw: str) -> list:
    """
    Robustly extract a JSON array from LLM output that may contain
    preamble text, markdown fences, or other noise.
    """
    # 1. Strip markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()

    # 2. Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3. Find the first [ ... ] block in the text
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return []


def extract_triples(episodes: list[dict]) -> list[dict]:
    conversation = "\n".join(
        f"{e['role'].upper()}: {e['content']}" for e in episodes
    )

    prompt = EXTRACTION_PROMPT.format(conversation=conversation)

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json().get("response", "[]").strip()

    triples = _extract_json_array(raw)

    valid = [t for t in triples if all(k in t for k in ("subject", "predicate", "object"))]

    if not valid:
        print(f"[extractor] No valid triples found in response:\n{raw[:300]}")
    else:
        print(f"[extractor] Extracted {len(valid)} triples: {valid}")

    return valid