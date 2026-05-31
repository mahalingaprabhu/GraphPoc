"""
Memory Retriever — Neo4j Query Layer
======================================
One method per memory type.
The LangGraph agent will call these to fetch context before answering.

Memory types covered:
  - Transactional  : order history, items, payments
  - Temporal       : time-based order patterns
  - Behavioral     : payment behavior, purchase patterns
  - Preference     : derived preferred payment, favorite category
  - Emotional      : review sentiment history
  - Relationship   : seller relationships, product chains
  - Semantic       : canonical world facts
"""

from neo4j import GraphDatabase
from typing import Optional


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NEO4J_URI      = "bolt://127.0.0.1:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "Prabhu13"


# ─────────────────────────────────────────────
# MEMORY RETRIEVER
# ─────────────────────────────────────────────
class MemoryRetriever:
    """
    Wraps all Neo4j memory queries.
    Each method returns a plain dict or list of dicts
    so the LangGraph agent can directly use the results.
    """

    def __init__(self, uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("✅ MemoryRetriever connected to Neo4j")

    def close(self):
        self.driver.close()

    def _run(self, query: str, **params) -> list[dict]:
        """Internal helper — runs a Cypher query and returns list of dicts."""
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]

    # ─────────────────────────────────────────
    # 1. TRANSACTIONAL MEMORY
    #    "What did this customer buy?"
    # ─────────────────────────────────────────
    def get_order_history(self, customer_unique_id: str) -> list[dict]:
        """
        Returns all orders placed by a customer with
        status, purchase date, and item count.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
            OPTIONAL MATCH (o)-[:HAS_ITEM]->(oi:OrderItem)
            RETURN o.order_id          AS order_id,
                   o.status            AS status,
                   o.purchase_timestamp AS purchased_at,
                   o.year              AS year,
                   o.month             AS month,
                   count(oi)           AS item_count
            ORDER BY o.purchase_timestamp DESC
        """, uid=customer_unique_id)

    def get_order_items(self, order_id: str) -> list[dict]:
        """
        Returns all items in a specific order with
        product category, seller, price.
        """
        return self._run("""
            MATCH (o:Order {order_id: $oid})-[:HAS_ITEM]->(oi:OrderItem)
                  -[:IS_PRODUCT]->(p:Product)-[:BELONGS_TO]->(cat:Category)
            MATCH (oi)-[:FULFILLED_BY]->(s:Seller)
            RETURN p.product_id  AS product_id,
                   cat.name      AS category,
                   s.seller_id   AS seller_id,
                   s.city        AS seller_city,
                   oi.price      AS price,
                   oi.freight_value AS freight
        """, oid=order_id)

    # ─────────────────────────────────────────
    # 2. TEMPORAL MEMORY
    #    "When did things happen? Any patterns over time?"
    # ─────────────────────────────────────────
    def get_purchase_timeline(self, customer_unique_id: str) -> list[dict]:
        """
        Returns monthly purchase counts for a customer.
        Used to detect buying frequency patterns.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
            RETURN o.year  AS year,
                   o.month AS month,
                   count(o) AS orders
            ORDER BY o.year, o.month
        """, uid=customer_unique_id)

    def get_late_deliveries(self, customer_unique_id: str) -> list[dict]:
        """
        Returns orders where delivery was late.
        Temporal comparison: actual vs estimated delivery.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
            WHERE o.delivered_customer_date > o.estimated_delivery_date
              AND o.delivered_customer_date <> 'NaT'
              AND o.estimated_delivery_date <> 'NaT'
            RETURN o.order_id                 AS order_id,
                   o.estimated_delivery_date  AS estimated,
                   o.delivered_customer_date  AS actual,
                   o.status                   AS status
        """, uid=customer_unique_id)

    def get_orders_by_period(self, year: int, month: Optional[int] = None) -> list[dict]:
        """
        Returns order volume for a given year/month.
        Used for global temporal patterns.
        """
        if month:
            return self._run("""
                MATCH (o:Order {year: $year, month: $month})
                RETURN count(o) AS order_count, $year AS year, $month AS month
            """, year=year, month=month)
        else:
            return self._run("""
                MATCH (o:Order {year: $year})
                RETURN o.month AS month, count(o) AS order_count
                ORDER BY o.month
            """, year=year)

    # ─────────────────────────────────────────
    # 3. BEHAVIORAL MEMORY
    #    "How does this customer behave?"
    # ─────────────────────────────────────────
    def get_payment_behavior(self, customer_unique_id: str) -> list[dict]:
        """
        Returns all payment types used by a customer with counts.
        Reveals payment behavior patterns.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
                  -[r:PAID_WITH]->(pm:PaymentMethod)
            RETURN pm.type       AS payment_type,
                   count(o)      AS times_used,
                   avg(r.value)  AS avg_order_value,
                   avg(r.installments) AS avg_installments
            ORDER BY times_used DESC
        """, uid=customer_unique_id)

    def get_category_behavior(self, customer_unique_id: str) -> list[dict]:
        """
        Returns product categories a customer buys from, with counts.
        Reveals shopping behavior.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
                  -[:HAS_ITEM]->(oi:OrderItem)-[:IS_PRODUCT]->(p:Product)
                  -[:BELONGS_TO]->(cat:Category)
            RETURN cat.name   AS category,
                   count(oi)  AS items_bought,
                   sum(oi.price) AS total_spent
            ORDER BY items_bought DESC
        """, uid=customer_unique_id)

    # ─────────────────────────────────────────
    # 4. PREFERENCE MEMORY
    #    "What does this customer prefer?"
    # ─────────────────────────────────────────
    def get_customer_preferences(self, customer_unique_id: str) -> dict:
        """
        Returns derived preference facts stored on the Customer node.
        preferred_payment is pre-computed during data load.
        """
        results = self._run("""
            MATCH (c:Customer {unique_id: $uid})
            RETURN c.unique_id          AS customer_id,
                   c.preferred_payment  AS preferred_payment,
                   c.city               AS city,
                   c.state              AS state
        """, uid=customer_unique_id)
        return results[0] if results else {}

    def get_favorite_category(self, customer_unique_id: str) -> dict:
        """
        Derives favorite category from purchase history.
        Returns top category by items bought.
        """
        results = self.get_category_behavior(customer_unique_id)
        return results[0] if results else {}

    def get_customer_profile(self, customer_unique_id: str) -> dict:
        """
        Full preference profile — combines all preference signals.
        This is the main method the agent calls for personalization.
        """
        prefs    = self.get_customer_preferences(customer_unique_id)
        fav_cat  = self.get_favorite_category(customer_unique_id)
        orders   = self.get_order_history(customer_unique_id)

        return {
            "customer_id"        : customer_unique_id,
            "location"           : f"{prefs.get('city', '?')}, {prefs.get('state', '?')}",
            "preferred_payment"  : prefs.get("preferred_payment", "unknown"),
            "favorite_category"  : fav_cat.get("category", "unknown"),
            "total_orders"       : len(orders),
            "total_spent"        : sum(
                item.get("price", 0) or 0
                for order in orders
                for item in self.get_order_items(order["order_id"])
            ),
        }

    # ─────────────────────────────────────────
    # 5. EMOTIONAL MEMORY
    #    "How does this customer feel about their experience?"
    # ─────────────────────────────────────────
    def get_review_history(self, customer_unique_id: str) -> list[dict]:
        """
        Returns all reviews written by a customer with
        sentiment label and score.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:WROTE]->(r:Review)
                  -[:ABOUT]->(o:Order)
            RETURN r.review_id  AS review_id,
                   r.score      AS score,
                   r.sentiment  AS sentiment,
                   r.title      AS title,
                   o.order_id   AS order_id
            ORDER BY r.score ASC
        """, uid=customer_unique_id)

    def get_emotional_summary(self, customer_unique_id: str) -> dict:
        """
        Summarizes emotional state of a customer.
        Returns counts of positive/neutral/negative reviews
        and an overall sentiment label.
        """
        reviews = self.get_review_history(customer_unique_id)
        if not reviews:
            return {"overall": "unknown", "positive": 0, "neutral": 0, "negative": 0}

        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for r in reviews:
            sentiment = r.get("sentiment", "neutral")
            counts[sentiment] = counts.get(sentiment, 0) + 1

        total = len(reviews)
        dominant = max(counts, key=counts.get)
        return {
            "overall"  : dominant,
            "positive" : counts["positive"],
            "neutral"  : counts["neutral"],
            "negative" : counts["negative"],
            "total"    : total,
            "avg_score": round(sum(r["score"] for r in reviews) / total, 2),
        }

    # ─────────────────────────────────────────
    # 6. RELATIONSHIP MEMORY
    #    "Who is connected to whom?"
    # ─────────────────────────────────────────
    def get_seller_relationships(self, customer_unique_id: str) -> list[dict]:
        """
        Returns sellers a customer has bought from.
        """
        return self._run("""
            MATCH (c:Customer {unique_id: $uid})-[:PLACED]->(o:Order)
                  -[:HAS_ITEM]->(oi:OrderItem)-[:FULFILLED_BY]->(s:Seller)
            RETURN s.seller_id  AS seller_id,
                   s.city       AS seller_city,
                   s.state      AS seller_state,
                   count(oi)    AS items_bought
            ORDER BY items_bought DESC
        """, uid=customer_unique_id)

    def get_product_relationships(self, product_id: str) -> dict:
        """
        Returns what a product is connected to —
        category, sellers who sell it, customers who bought it.
        """
        results = self._run("""
            MATCH (p:Product {product_id: $pid})
            OPTIONAL MATCH (p)-[:BELONGS_TO]->(cat:Category)
            OPTIONAL MATCH (oi:OrderItem)-[:IS_PRODUCT]->(p)
            OPTIONAL MATCH (oi)-[:FULFILLED_BY]->(s:Seller)
            RETURN p.product_id     AS product_id,
                   cat.name         AS category,
                   count(DISTINCT s) AS seller_count,
                   count(oi)         AS times_ordered
        """, pid=product_id)
        return results[0] if results else {}

    # ─────────────────────────────────────────
    # 7. SEMANTIC MEMORY
    #    "What are canonical facts about this concept?"
    # ─────────────────────────────────────────
    def get_semantic_facts(self, concept: str) -> list[dict]:
        """
        Returns canonical facts about a concept from semantic memory.
        e.g. get_semantic_facts('boleto') →
             [{'subject': 'boleto', 'relation': 'IS_A', 'object': 'PaymentInstrument'}]
        """
        return self._run("""
            MATCH (s:SemanticNode {name: $concept})-[r:SEMANTIC_RELATION]->(o:SemanticNode)
            RETURN s.name  AS subject,
                   r.type  AS relation,
                   o.name  AS object
            UNION
            MATCH (s:SemanticNode)-[r:SEMANTIC_RELATION]->(o:SemanticNode {name: $concept})
            RETURN s.name  AS subject,
                   r.type  AS relation,
                   o.name  AS object
        """, concept=concept)

    def get_all_semantic_facts(self) -> list[dict]:
        """Returns all seeded semantic facts."""
        return self._run("""
            MATCH (s:SemanticNode)-[r:SEMANTIC_RELATION]->(o:SemanticNode)
            RETURN s.name AS subject, r.type AS relation, o.name AS object
        """)

    # ─────────────────────────────────────────
    # 8. COMBINED — Agent context builder
    #    Single call to get everything the agent
    #    needs before answering about a customer
    # ─────────────────────────────────────────
    def get_full_customer_context(self, customer_unique_id: str) -> dict:
        """
        Master method — returns all memory types for a customer
        in one structured dict. The LangGraph agent passes this
        as context to the LLM before generating a response.
        """
        return {
            "profile"           : self.get_customer_preferences(customer_unique_id),
            "order_history"     : self.get_order_history(customer_unique_id),
            "payment_behavior"  : self.get_payment_behavior(customer_unique_id),
            "category_behavior" : self.get_category_behavior(customer_unique_id),
            "emotional_summary" : self.get_emotional_summary(customer_unique_id),
            "seller_relations"  : self.get_seller_relationships(customer_unique_id),
            "late_deliveries"   : self.get_late_deliveries(customer_unique_id),
        }


# ─────────────────────────────────────────────
# QUICK TEST — run this file directly to verify
# ─────────────────────────────────────────────
if __name__ == "__main__":
    retriever = MemoryRetriever()

    # Pick a real customer_unique_id from your Neo4j
    # Run this in Neo4j Browser first to get one:
    # MATCH (c:Customer) RETURN c.unique_id LIMIT 1
    TEST_CUSTOMER = "REPLACE_WITH_REAL_CUSTOMER_UNIQUE_ID"

    print("\n── 1. TRANSACTIONAL MEMORY ──────────────────")
    orders = retriever.get_order_history(TEST_CUSTOMER)
    print(f"Orders found: {len(orders)}")
    for o in orders[:3]:
        print(f"  {o}")

    print("\n── 2. TEMPORAL MEMORY ───────────────────────")
    timeline = retriever.get_purchase_timeline(TEST_CUSTOMER)
    for t in timeline:
        print(f"  {t}")

    print("\n── 3. BEHAVIORAL MEMORY ─────────────────────")
    payments = retriever.get_payment_behavior(TEST_CUSTOMER)
    for p in payments:
        print(f"  {p}")

    print("\n── 4. PREFERENCE MEMORY ─────────────────────")
    profile = retriever.get_customer_preferences(TEST_CUSTOMER)
    print(f"  {profile}")

    print("\n── 5. EMOTIONAL MEMORY ──────────────────────")
    emotion = retriever.get_emotional_summary(TEST_CUSTOMER)
    print(f"  {emotion}")

    print("\n── 6. RELATIONSHIP MEMORY ───────────────────")
    sellers = retriever.get_seller_relationships(TEST_CUSTOMER)
    for s in sellers:
        print(f"  {s}")

    print("\n── 7. SEMANTIC MEMORY ───────────────────────")
    facts = retriever.get_semantic_facts("boleto")
    for f in facts:
        print(f"  {f}")

    print("\n── 8. FULL CUSTOMER CONTEXT ─────────────────")
    context = retriever.get_full_customer_context(TEST_CUSTOMER)
    for memory_type, data in context.items():
        print(f"  {memory_type}: {data}")

    retriever.close()