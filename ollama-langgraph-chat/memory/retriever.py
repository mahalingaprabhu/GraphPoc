from memory.neo4j_store import driver
from config.settings import NEO4J_HOP_DEPTH


def _extract_keywords(message: str) -> list[str]:
    """Simple keyword extraction — split and filter stopwords."""
    stopwords = {
        "i", "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "have", "has", "do", "does", "did", "will", "would", "could", "should",
        "what", "how", "why", "when", "where", "who", "which", "that", "this",
        "it", "in", "on", "at", "to", "for", "of", "and", "or", "but", "not",
        "can", "me", "my", "you", "your", "we", "our", "tell", "about", "any",
        "please", "help", "want", "need", "know", "think", "use", "using"
    }
    words = message.lower().replace("?", "").replace("!", "").split()
    return [w for w in words if w not in stopwords and len(w) > 2]


def get_relevant_triples(message: str) -> list[dict]:
    """
    Query Neo4j for triples relevant to the current message.
    Strategy:
      1. Always include User's direct connections
      2. Also include any entity matching keywords in the message
    """
    keywords = _extract_keywords(message)
    triples = []

    with driver.session() as session:
        # Always fetch User's direct neighbourhood
        result = session.run(
            """
            MATCH (u:Entity {name: "User"})-[r:RELATES]->(o:Entity)
            RETURN u.name AS subject, r.type AS predicate, o.name AS object
            """,
        )
        triples += [{"subject": r["subject"], "predicate": r["predicate"],
                     "object": r["object"]} for r in result]

        # Also fetch Prabhu node if exists
        result = session.run(
            """
            MATCH (u:Entity {name: "Prabhu"})-[r:RELATES]->(o:Entity)
            RETURN u.name AS subject, r.type AS predicate, o.name AS object
            """,
        )
        triples += [{"subject": r["subject"], "predicate": r["predicate"],
                     "object": r["object"]} for r in result]

        # Fetch entities matching keywords in current message
        if keywords:
            result = session.run(
                """
                MATCH (s:Entity)-[r:RELATES]->(o:Entity)
                WHERE any(kw IN $keywords WHERE
                    toLower(s.name) CONTAINS kw OR
                    toLower(o.name) CONTAINS kw)
                RETURN s.name AS subject, r.type AS predicate, o.name AS object
                LIMIT 10
                """,
                keywords=keywords,
            )
            triples += [{"subject": r["subject"], "predicate": r["predicate"],
                         "object": r["object"]} for r in result]

    # Deduplicate
    seen = set()
    unique = []
    for t in triples:
        key = (t["subject"], t["predicate"], t["object"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    return unique


def build_memory_context(message: str) -> str:
    """
    Build natural language memory context from relevant KG triples.
    Injected into the system prompt at query time.
    """
    triples = get_relevant_triples(message)
    if not triples:
        return ""

    # Convert triples → natural language sentences
    predicate_map = {
        "INTERESTED_IN":  "is interested in",
        "ASKED_ABOUT":    "has asked about",
        "USES":           "uses",
        "OWNS":           "owns",
        "WORKS_ON":       "is working on",
        "KNOWS":          "knows about",
        "VISITED":        "has visited",
        "PLANS_TO_VISIT": "is planning to visit",
        "ASKS_ABOUT":     "has been asking about",
        "PART_OF":        "is part of",
        "RELATES":        "is related to",
    }

    lines = []
    for t in triples:
        pred_text = predicate_map.get(t["predicate"], t["predicate"].lower().replace("_", " "))
        lines.append(f"- {t['subject']} {pred_text} {t['object']}.")

    context = "## What I know about the user:\n" + "\n".join(lines)
    return context