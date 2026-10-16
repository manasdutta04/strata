"""Load the synthetic Northwind dataset into FalkorDB.

Usage (from backend/):  python seed.py
Historical reversals are applied through the real `supersede` template (Q3), not by hand.
"""
import json
from pathlib import Path

from embeddings import embed
from graph.schema import ensure_schema
from graph.service import GraphService

DATA = Path(__file__).parent.parent / "data" / "northwind" / "northwind.json"
LIVE_REVERSAL_ARGS = None


def _props(p: dict) -> dict:
    return {k: v for k, v in p.items() if v is not None}


def load(svc: GraphService) -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    svc.reset()
    ensure_schema(svc)

    for n in data["nodes"]:
        svc.raw(f"CREATE (n:{n['label']}) SET n = $p", {"p": _props(n["props"])})

    for e in data["edges"]:
        (sl, sid), (dl, did) = e["src"], e["dst"]
        svc.raw(
            f"MATCH (a:{sl} {{id: $a}}), (b:{dl} {{id: $b}}) CREATE (a)-[r:{e['type']}]->(b) SET r += $p",
            {"a": sid, "b": did, "p": e["props"]},
        )

    # Chunks: one per paragraph of each doc, plus one per evidence message; embedded locally.
    chunks: list[tuple[str, str, str, str]] = []  # (chunk_id, source_label, source_id, text)
    for src_id, body in data["chunk_sources"].items():
        for i, para in enumerate(p for p in body.split("\n\n") if p.strip()):
            chunks.append((f"{src_id}#{i}", "Doc", src_id, para.strip()))
    ev = svc.raw("MATCH (:Decision)-[:EVIDENCED_BY]->(m:Message) RETURN DISTINCT m.id, m.text").result_set
    for mid, text in ev:
        chunks.append((f"{mid}#0", "Message", mid, text))
    vectors = embed([c[3] for c in chunks])
    for (cid, sl, sid, text), vec in zip(chunks, vectors):
        svc.raw(
            f"MATCH (s:{sl} {{id: $sid}}) CREATE (s)-[:HAS_CHUNK]->(:Chunk {{id: $cid, text: $text, source_id: $sid, embedding: vecf32($vec)}})",
            {"sid": sid, "cid": cid, "text": text, "vec": vec},
        )
    # Decisions are evidenced by the chunk of their evidence document/message too.
    svc.raw("MATCH (d:Decision)-[:EVIDENCED_BY]->(s)-[:HAS_CHUNK]->(c:Chunk) MERGE (d)-[:EVIDENCED_BY]->(c)")

    svc.run("build_collaboration")
    for new, old in data["supersessions"]:
        svc.run("supersede", new_id=new, old_id=old)
    return {"nodes": len(data["nodes"]), "edges": len(data["edges"]), "chunks": len(chunks)}


if __name__ == "__main__":
    print(load(GraphService()))
