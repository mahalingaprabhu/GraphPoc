from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def write_triples(triples: list[dict]):
    """
    Each triple: {subject, predicate, object}
    Creates nodes with MERGE (no duplicates on exact name match).
    Phase 2 will add fuzzy ER on top of this.
    """
    with driver.session() as session:
        for t in triples:
            session.run(
                """
                MERGE (s:Entity {name: $subject})
                MERGE (o:Entity {name: $object})
                MERGE (s)-[r:RELATES {type: $predicate}]->(o)
                ON CREATE SET r.count = 1
                ON MATCH  SET r.count = r.count + 1
                """,
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"],
            )


def get_neighbourhood(entity: str = "User", hops: int = 2) -> list[dict]:
    """Return all triples within N hops of an entity."""
    with driver.session() as session:
        result = session.run(
            f"""
            MATCH path = (start:Entity {{name: $entity}})-[*1..{hops}]-(end:Entity)
            UNWIND relationships(path) AS r
            RETURN startNode(r).name AS subject,
                   r.type           AS predicate,
                   endNode(r).name  AS object
            """,
            entity=entity,
        )
        return [{"subject": r["subject"], "predicate": r["predicate"], "object": r["object"]}
                for r in result]


def get_all_triples() -> list[dict]:
    """For the graph visualiser panel."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (s:Entity)-[r:RELATES]->(o:Entity)
            RETURN s.name AS subject, r.type AS predicate, o.name AS object, r.count AS count
            """
        )
        return [{"subject": r["subject"], "predicate": r["predicate"],
                 "object": r["object"], "count": r["count"]} for r in result]


def close():
    driver.close()