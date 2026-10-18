"""Pre-recording warm-up. Run from backend/:  python demo_warmup.py

1. Reseeds the graph and checks the golden questions.
2. Runs the real live-reversal pipeline once so every LLM response (extraction + 5 fix drafts) is cached
   in .llm_cache. The recorded run then replays identical prompts instantly. This is a replay of a real
   earlier model response, which the README discloses.
3. Asserts the demo contract: exactly 3 docs + 2 tickets, an owner and a draft for each.
   Then warms the doc check (one contradiction caught) and the self-audit's 7 fix drafts the same way.
4. Reseeds again and deletes per-user memory graphs, leaving a clean slate for the take.
5. Reports whether the backend, web app and FalkorDB are reachable.

Exit code is non-zero if anything is not ready.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from agents import concierge, pipeline, steward
from agents.ingestor import IngestDoc, IngestMessage
from embeddings import embed
from graph.service import GraphService
from seed import load

LIVE = json.loads((Path(__file__).parent.parent / "data" / "northwind" / "live_reversal.json").read_text())
GOLDEN = [
    ("Why do we use Postgres for sessions?", lambda a: a.found and "Postgres" in a.text and "Redis" in a.text),
    ("Why did we use Redis for sessions? (as of April)", lambda a: "later superseded" in a.text),
    ("Who knows the billing reconciler?", lambda a: "Priya" in a.segments[0].text and "Bus-factor warning" in a.text),
    ("Who connects Payments and Data?", lambda a: "Reyes" in a.text),
    ("Why is the event bus on Kafka?", lambda a: a.found and "Kafka" in a.segments[0].text),
    ("How do we deploy?", lambda a: a.tool == "search" and any(s.tone == "warning" and "D-04" in s.text for s in a.segments)),
    ("Who owns the onboarding doc?", lambda a: "Sofia Alvarez" in a.text and any(s.tone == "warning" for s in a.segments)),
    ("What changed since June?", lambda a: a.found and "GitHub Actions" in a.text),
    ("What does Aisha work on?", lambda a: a.tool == "person" and "Platform Lead" in a.text),
    ("Which docs are out of date?", lambda a: a.found and a.segments[0].text.startswith("7 items")),
]
DOC = IngestDoc(title="Local dev setup for auth-service", author="omar", text=(
    "Getting auth-service running on your laptop.\n\n"
    "Start a local Redis first: user sessions are stored in Redis, so login will fail without it.\n\n"
    "Access tokens expire after 15 minutes, so expect to log in again during long debugging sessions.\n\n"
    "Pushes run CI on GitHub Actions; check the Actions tab if your branch is red."))  # same text as the UI's example
problems: list[str] = []


def step(msg: str) -> None:
    print(f"\n== {msg}", flush=True)


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}", flush=True)
    if not ok:
        problems.append(label)


def reachable(url: str) -> bool:
    try:
        return urllib.request.urlopen(url, timeout=4).status == 200
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    step("FalkorDB")
    try:
        svc = GraphService()
        svc.raw("RETURN 1")
        check(True, "FalkorDB reachable")
    except Exception as e:  # noqa: BLE001
        check(False, "FalkorDB reachable", f"{e} (is Docker Desktop running? `docker compose up -d`)")
        return 1

    step("Warming the local embedding model")
    embed(["warm up"])
    check(True, "embedding model loaded")

    step("Reseed and golden questions")
    print(f"  seeded: {load(svc)}")
    for q, ok in GOLDEN:
        t = time.time()
        a = concierge.answer(svc, q)
        dt = time.time() - t
        check(ok(a) and dt < 3, q, f"{dt:.2f}s")

    step("Live reversal through the real pipeline (first run may take ~20s while the CLI answers; then it is cached)")
    t = time.time()
    r = pipeline.ingest(svc, IngestMessage(channel=LIVE["channel"], author=LIVE["author"], text=LIVE["text"]))
    print(f"  pipeline took {time.time() - t:.1f}s")
    check(r.get("status") == "ingested", "message recognised as a decision", str(r.get("extraction", {}).get("summary", "")))
    check(r.get("supersedes_id") == "D-07", "supersedes the Kafka decision (D-07)", str(r.get("supersedes_id")))
    check((r.get("docs"), r.get("tickets")) == (3, 2), "exactly 3 docs + 2 tickets stale", f"{r.get('docs')} docs, {r.get('tickets')} tickets")
    tasks = r.get("tasks", [])
    check(bool(tasks) and all(x["owner_id"] and x["draft"] for x in tasks), "every item has an owner and a drafted diff")

    step("Replay timing (everything should now be cached)")
    svc2 = GraphService()
    load(svc2)
    t = time.time()
    r2 = pipeline.ingest(svc2, IngestMessage(channel=LIVE["channel"], author=LIVE["author"], text=LIVE["text"]))
    dt = time.time() - t
    check(dt < 8 and (r2.get("docs"), r2.get("tickets")) == (3, 2), "second run is fast and identical", f"{dt:.1f}s")

    step("New-doc contradiction check and self-audit (warms their LLM calls)")
    load(svc)
    d = pipeline.ingest_doc(svc, DOC)
    bad = [(c["claim_id"], c["closed_by"]) for c in d["checks"] if not c["in_force"]]
    check(bad == [("C-01", "D-02")], "doc check flags the Redis sessions sentence (closed by D-02)", str(bad))
    load(svc)
    audit = steward.audit(svc)
    check(len(audit) == 7 and all(x["draft"] for x in audit), "self-audit drafts a fix for all 7 pre-existing contradictions", str(len(audit)))

    step("Clean slate for the take")
    svc.reset_user_graphs()
    load(svc)
    check(not svc.run("inbox"), "inbox is empty")
    check(svc.run("resume_tasks") == [], "no unfinished tasks")

    step("Servers")
    check(reachable("http://localhost:8000/health"), "backend on :8000", "uvicorn app.main:app --port 8000")
    check(reachable("http://localhost:3000"), "web on :3000", "cd web && npm run dev")

    print("\n" + ("READY to record." if not problems else f"NOT READY: {len(problems)} problem(s): " + "; ".join(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
