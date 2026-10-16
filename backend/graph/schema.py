"""Index creation for the `strata` graph. Idempotent: existing indexes are skipped."""
from config import settings
from graph.service import GraphService

INDEXES = [
    "CREATE INDEX FOR (p:Person) ON (p.id)",
    "CREATE INDEX FOR (s:System) ON (s.id)",
    "CREATE INDEX FOR (d:Decision) ON (d.id)",
    "CREATE INDEX FOR (c:Claim) ON (c.id)",
    "CREATE INDEX FOR (d:Doc) ON (d.id)",
    "CREATE INDEX FOR (t:Ticket) ON (t.id)",
    "CREATE INDEX FOR (t:Task) ON (t.id)",
    "CREATE INDEX FOR (t:Task) ON (t.status)",
    "CREATE INDEX FOR (m:Message) ON (m.id)",
    f"CREATE VECTOR INDEX FOR (c:Chunk) ON (c.embedding) "
    f"OPTIONS {{dimension: {settings.embedding_dim}, similarityFunction: 'cosine'}}",
    "CALL db.idx.fulltext.createNodeIndex('Doc', 'title')",
    "CALL db.idx.fulltext.createNodeIndex('Message', 'text')",
]


def ensure_schema(svc: GraphService) -> None:
    for stmt in INDEXES:
        try:
            svc.raw(stmt)
        except Exception as e:  # noqa: BLE001
            if "already indexed" not in str(e).lower() and "already exists" not in str(e).lower():
                raise
