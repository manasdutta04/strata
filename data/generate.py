"""Deterministic generator for Northwind Labs, a SYNTHETIC 25-person engineering company.

Writes data/northwind/northwind.json and data/northwind/live_reversal.json.
Every demo beat is encoded here; nothing is random across runs (fixed seed).
"""
import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "northwind"
rng = random.Random(42)


def ts(s: str) -> int:
    """'2026-03-10' or '2026-03-10T09:30' -> epoch ms (UTC)."""
    fmt = "%Y-%m-%dT%H:%M" if "T" in s else "%Y-%m-%d"
    return int(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)


nodes: list[dict] = []
edges: list[dict] = []


def node(label: str, id_: str, **props) -> str:
    nodes.append({"label": label, "id": id_, "props": {"id": id_, **props}})
    return id_


def edge(typ: str, src: tuple[str, str], dst: tuple[str, str], **props) -> None:
    edges.append({"type": typ, "src": list(src), "dst": list(dst), "props": props})


# ---------------------------------------------------------------- org
TEAMS = ["Platform", "Payments", "Growth", "Data", "Mobile"]
PEOPLE = {  # id: (name, team, role)
    "aisha": ("Aisha Rahman", "Platform", "Platform Lead"),
    "leo": ("Leo Park", "Platform", "Senior Engineer"),
    "mei": ("Mei Lin Chen", "Platform", "Engineer"),
    "omar": ("Omar Haddad", "Platform", "Engineer"),
    "sofia": ("Sofia Alvarez", "Platform", "Engineer"),
    "daniel": ("Daniel Okafor", "Payments", "Payments Lead"),
    "priya": ("Priya Nair", "Payments", "Senior Engineer"),
    "hannah": ("Hannah Weiss", "Payments", "Engineer"),
    "raj": ("Raj Patel", "Payments", "Engineer"),
    "lucia": ("Lucia Moretti", "Payments", "Engineer"),
    "nina": ("Nina Kowalski", "Growth", "Growth Lead"),
    "ben": ("Ben Carter", "Growth", "Engineer"),
    "yuki": ("Yuki Tanaka", "Growth", "Engineer"),
    "carlos": ("Carlos Mendes", "Growth", "Engineer"),
    "ella": ("Ella Brooks", "Growth", "Engineer"),
    "tomas": ("Tomás Reyes", "Data", "Senior Data Engineer"),
    "grace": ("Grace Liu", "Data", "Data Lead"),
    "ivan": ("Ivan Petrov", "Data", "Data Engineer"),
    "amara": ("Amara Nwosu", "Data", "Data Engineer"),
    "felix": ("Felix Berg", "Data", "Data Engineer"),
    "jon": ("Jon Silva", "Mobile", "Mobile Lead"),
    "kavya": ("Kavya Menon", "Mobile", "Engineer"),
    "theo": ("Theo Larsen", "Mobile", "Engineer"),
    "zara": ("Zara Khan", "Mobile", "Engineer"),
    "noah": ("Noah Fischer", "Mobile", "Engineer"),
}
SYSTEMS = {  # id: (kind, owning team, channel, contributors weighted by order)
    "auth-service": ("service", "Platform", "platform", ["aisha", "leo", "mei", "omar"]),
    "session-store": ("infra", "Platform", "platform", ["leo", "mei", "sofia"]),
    "billing-api": ("service", "Payments", "payments", ["daniel", "hannah", "raj", "lucia"]),
    "billing-reconciler": ("service", "Payments", "payments", ["priya"]),
    "event-bus": ("infra", "Platform", "platform", ["omar", "aisha", "sofia", "leo"]),
    "public-api-v1": ("service", "Growth", "growth", ["nina", "carlos", "ella", "ben"]),
    "mobile-app": ("service", "Mobile", "mobile", ["jon", "kavya", "zara", "noah", "theo"]),
    "ci-pipeline": ("infra", "Platform", "platform", ["mei", "omar", "sofia"]),
}

for t in TEAMS:
    node("Team", t.lower(), name=t)
for pid, (name, team, role) in PEOPLE.items():
    node("Person", pid, name=name, handle=f"@{pid}", role=role)
    edge("MEMBER_OF", ("Person", pid), ("Team", team.lower()))
for sid, (kind, team, _, _) in SYSTEMS.items():
    node("System", sid, name=sid, kind=kind)
    edge("OWNS", ("Team", team.lower()), ("System", sid))
for a in ("Ingestor", "Steward", "Concierge"):
    node("Agent", a.lower(), name=a)

# ---------------------------------------------------------------- decisions & claims
DECISIONS = {  # id: (summary, rationale, from, by, system, claim text)
    "D-01": ("Store user sessions in Redis", "Fast reads, simple TTL expiry for session tokens.",
             "2026-03-10", "aisha", "session-store", "Sessions are stored in Redis."),
    "D-02": ("Move session storage from Redis to Postgres", "Redis memory cost is too high and sessions need durability across restarts.",
             "2026-08-14", "leo", "session-store", "Sessions are stored in Postgres."),
    "D-03": ("Run CI on Jenkins", "Existing Jenkins server and plugins already in place.",
             "2026-01-15", "mei", "ci-pipeline", "CI runs on Jenkins."),
    "D-04": ("Migrate CI from Jenkins to GitHub Actions", "Jenkins maintenance load and flaky agents; Actions is closer to the code.",
             "2026-06-02", "mei", "ci-pipeline", "CI runs on GitHub Actions."),
    "D-05": ("Public API v1 is the supported external API", "Single stable surface for partners and the mobile app.",
             "2026-02-01", "nina", "public-api-v1", "Public API v1 is the supported public API and new features may build on it."),
    "D-06": ("Deprecate Public API v1; sunset on 2026-12-01", "v2 ships typed errors and pagination; maintaining two surfaces is unsustainable.",
             "2026-07-20", "nina", "public-api-v1", "Public API v1 is deprecated and will be shut down on 2026-12-01."),
    "D-07": ("Use Kafka as the event bus", "Durable ordered log and a mature consumer ecosystem.",
             "2026-02-20", "aisha", "event-bus", "The event bus runs on Kafka."),
    "D-08": ("Reconcile billing nightly in a batch job", "Simplest way to match processor payouts with ledger entries.",
             "2026-04-05", "priya", "billing-reconciler", "Billing reconciliation runs as a nightly batch."),
    "D-09": ("Mobile app talks to the backend over REST", "Team familiarity and existing public API.",
             "2026-03-25", "jon", "mobile-app", "The mobile app uses REST, not GraphQL."),
    "D-10": ("Access tokens expire after 15 minutes", "Limits blast radius of a leaked token.",
             "2026-05-12", "aisha", "auth-service", "Access tokens expire after 15 minutes."),
    "D-11": ("Billing API stays on Postgres 15", "Operational maturity and team skills.",
             "2026-04-18", "daniel", "billing-api", "The billing API stores data in Postgres 15."),
    "D-12": ("Mobile releases ship every two weeks", "Predictable cadence for store review.",
             "2026-05-30", "jon", "mobile-app", "Mobile releases ship every two weeks."),
}
SUPERSESSIONS = [["D-02", "D-01"], ["D-04", "D-03"], ["D-06", "D-05"]]  # [new, old]
CLAIM_OF = {d: f"C-{d[2:]}" for d in DECISIONS}
RECORDED_LAG = 3600 * 1000

for did, (summ, why, frm, by, sysid, claim) in DECISIONS.items():
    node("Decision", did, summary=summ, rationale=why, valid_from=ts(frm), valid_to=None,
         recorded_at=ts(frm) + RECORDED_LAG, confidence=0.95)
    node("Claim", CLAIM_OF[did], text=claim, valid_from=ts(frm), valid_to=None, recorded_at=ts(frm) + RECORDED_LAG)
    edge("DECIDED_BY", ("Decision", did), ("Person", by))
    edge("AFFECTS", ("Decision", did), ("System", sysid))
    edge("ESTABLISHES", ("Decision", did), ("Claim", CLAIM_OF[did]))
    edge("ABOUT", ("Claim", CLAIM_OF[did]), ("System", sysid))

# ---------------------------------------------------------------- messages
msg_n = 0
MESSAGES: dict[str, dict] = {}


def message(author: str, text: str, when: str, sysid: str | None = None, channel: str | None = None) -> str:
    global msg_n
    msg_n += 1
    mid = f"MSG-{msg_n:03d}"
    ch = channel or (SYSTEMS[sysid][2] if sysid else "eng")
    node("Message", mid, channel=ch, text=text, ts=ts(when))
    edge("AUTHORED", ("Person", author), ("Message", mid), ts=ts(when))
    if sysid:
        edge("ABOUT", ("Message", mid), ("System", sysid))
    MESSAGES[mid] = {"text": text}
    return mid


def evidence(did: str, mid: str) -> None:
    edge("EVIDENCED_BY", ("Decision", did), ("Message", mid))
    edge("EVIDENCED_BY", ("Claim", CLAIM_OF[did]), ("Message", mid))


# Evidence threads for every decision (the historical reversals get richer threads).
evidence("D-01", message("aisha", "Proposal: keep sessions in Redis. Reads are sub-millisecond and TTL expiry is free. Objections?", "2026-03-09T10:00", "session-store"))
evidence("D-01", message("leo", "No objection. Writing ADR-004 so it is on record.", "2026-03-10T09:00", "session-store"))
evidence("D-02", message("leo", "Redis is costing us about 40% more than planned and we lost sessions during the July failover. I propose moving sessions to Postgres.", "2026-08-12T11:00", "session-store"))
evidence("D-02", message("leo", "Decision: sessions move from Redis to Postgres. Cost and durability. ADR-004 is superseded, migration starts Monday.", "2026-08-14T10:00", "session-store"))
evidence("D-03", message("mei", "Staying on Jenkins for now, it already works for every repo.", "2026-01-15T14:00", "ci-pipeline"))
evidence("D-04", message("mei", "Jenkins agents flaked 11 times this month. Decision: we migrate CI to GitHub Actions, Jenkins is retired by end of July.", "2026-06-02T09:30", "ci-pipeline"))
evidence("D-05", message("nina", "v1 is the public API. Partners and the mobile app build against it.", "2026-02-01T10:00", "public-api-v1"))
evidence("D-06", message("nina", "Decision: Public API v1 is deprecated. Sunset date is 2026-12-01. New work goes to v2.", "2026-07-20T10:00", "public-api-v1"))
evidence("D-07", message("aisha", "We are going with Kafka for the event bus. Durable ordered log, strong consumer tooling.", "2026-02-20T10:00", "event-bus"))
evidence("D-08", message("priya", "Reconciliation will run nightly as a batch job. Simple and auditable.", "2026-04-05T15:00", "billing-reconciler"))
evidence("D-09", message("jon", "Mobile stays on REST against the public API. No GraphQL for now.", "2026-03-25T11:00", "mobile-app"))
evidence("D-10", message("aisha", "Access tokens will expire after 15 minutes, refresh tokens handle the rest.", "2026-05-12T10:00", "auth-service"))
evidence("D-11", message("daniel", "Billing API stays on Postgres 15, no migration planned.", "2026-04-18T10:00", "billing-api"))
evidence("D-12", message("jon", "Mobile releases ship every two weeks starting June.", "2026-05-30T10:00", "mobile-app"))

# Filler chatter: deterministic, per-system, dated across Mar-Oct.
CHAT = [
    "Reviewing the latest PR on {s}, looks good, small nit on naming.",
    "Heads up, {s} deploy is going out at 3pm.",
    "Anyone seen flaky tests around {s} this week?",
    "Pairing on {s} tomorrow morning if you want to join.",
    "Updated the dashboard for {s}, latency looks stable.",
    "Can someone take a look at the alert for {s}? It cleared itself but I want a second pair of eyes.",
    "Docs for {s} need a pass before the next onboarding cohort.",
    "Rolled back the change to {s}, will retry after more testing.",
    "Quick question about how {s} handles retries.",
    "Postmortem notes for the {s} blip are in the wiki.",
    "Planning the next sprint, {s} work is mostly maintenance.",
    "Thanks for the quick review on {s}!",
]
days = [f"2026-{m:02d}-{d:02d}T{h:02d}:00" for m in range(3, 11) for d in (3, 9, 15, 21, 27) for h in (10, 15)]
for sysid, (_, _, _, contrib) in SYSTEMS.items():
    for i in range(32):
        who = contrib[i % len(contrib)] if sysid != "billing-reconciler" else "priya"
        message(who, rng.choice(CHAT).format(s=sysid), rng.choice(days), sysid)

# ---------------------------------------------------------------- PRs (activity & collaboration)
pr_n = 0


def pr(author: str, reviewers: list[str], sysid: str, title: str, when: str) -> str:
    global pr_n
    pr_n += 1
    pid = f"PR-{pr_n:03d}"
    node("PR", pid, title=title, status="merged", merged_at=ts(when), url=f"https://github.example/northwind/{sysid}/pull/{pr_n}")
    edge("AUTHORED", ("Person", author), ("PR", pid), ts=ts(when))
    for r in reviewers:
        edge("REVIEWED", ("Person", r), ("PR", pid), ts=ts(when))
    edge("ABOUT", ("PR", pid), ("System", sysid))
    return pid


# Regular in-team PRs: each system has contributors who author and review one another.
plan = {"auth-service": 4, "session-store": 3, "billing-api": 4, "event-bus": 4, "public-api-v1": 3, "mobile-app": 3, "ci-pipeline": 3}
for sysid, n in plan.items():
    contrib = SYSTEMS[sysid][3]
    for i in range(n):
        a = contrib[i % len(contrib)]
        rev = [contrib[(i + 1) % len(contrib)]]
        pr(a, rev, sysid, f"{sysid}: change {i + 1}", days[(i * 7 + len(sysid)) % len(days)])

# Bus factor: billing-reconciler. Priya authors; every other person reviews at most twice (< threshold 3).
for i, rv in enumerate(["hannah", "raj", "tomas", "hannah", "raj", "tomas"]):
    pr("priya", [rv], "billing-reconciler", f"billing-reconciler: batch step {i + 1}", days[(i * 11 + 5) % len(days)])

# Knowledge bridge: Tomás reviews across Payments, Growth and Data; those teams barely touch otherwise.
for i, (a, s) in enumerate([("hannah", "billing-api"), ("raj", "billing-api"), ("carlos", "public-api-v1"), ("ella", "public-api-v1"),
                            ("ivan", "event-bus"), ("amara", "event-bus"), ("felix", "event-bus")]):
    pr(a, ["tomas"], s, f"{s}: data contract {i + 1}", days[(i * 9 + 3) % len(days)])
# Data engineers also review each other so Data forms its own cluster.
pr("ivan", ["amara"], "event-bus", "event-bus: consumer lag metrics", days[40])
pr("amara", ["felix"], "event-bus", "event-bus: replay tooling", days[44])
pr("grace", ["tomas"], "event-bus", "event-bus: analytics sink", days[50])

# Informal team: two Growth engineers (ben, yuki) and one Mobile engineer (theo) work tightly together.
for i, (a, rv) in enumerate([("ben", ["yuki", "theo"]), ("yuki", ["ben", "theo"]), ("theo", ["ben", "yuki"])] * 3):
    pr(a, rv, "mobile-app" if a == "theo" else "public-api-v1", f"cross-team feature {i + 1}", days[(i * 5 + 17) % len(days)])

# ---------------------------------------------------------------- docs
CHUNK_SRC: dict[str, str] = {}  # source node id -> text (loader chunks and embeds these)
doc_n = 0


def doc(id_: str, title: str, kind: str, body: str, sysid: str, owner: str | None, author: str,
        when: str, asserts: list[str] = (), cites: list[str] = (), evidence_for: str | None = None) -> str:
    node("Doc", id_, title=title, url=f"https://wiki.northwind.example/{id_}", kind=kind, version=1, updated_at=ts(when))
    edge("ABOUT", ("Doc", id_), ("System", sysid))
    edge("AUTHORED", ("Person", author), ("Doc", id_), ts=ts(when))
    if owner:
        edge("OWNS", ("Person", owner), ("Doc", id_))
    for c in asserts:
        edge("ASSERTS", ("Doc", id_), ("Claim", c))
    for d in cites:
        edge("CITES", ("Doc", id_), ("Decision", d))
    CHUNK_SRC[id_] = body
    if evidence_for:
        edge("EVIDENCED_BY", ("Decision", evidence_for), ("Doc", id_))
    return id_


# ADRs recording the decisions are *evidence*, not citations.
doc("ADR-004", "ADR-004: Sessions in Redis", "adr",
    "Context: we need a session store.\n\nDecision: sessions are stored in Redis with a 24 hour TTL.\n\nConsequences: Redis must be highly available.",
    "session-store", "aisha", "leo", "2026-03-10")
edge("EVIDENCED_BY", ("Decision", "D-01"), ("Doc", "ADR-004"))
doc("ADR-007", "ADR-007: Kafka as the event bus", "adr",
    "Context: services need a durable event log.\n\nDecision: the event bus runs on Kafka.\n\nConsequences: operate a Kafka cluster and a schema registry.",
    "event-bus", "aisha", "aisha", "2026-02-20")
edge("EVIDENCED_BY", ("Decision", "D-07"), ("Doc", "ADR-007"))

# --- stale after the historical session reversal (D-02 supersedes D-01)
doc("DOC-onboarding", "Engineering Onboarding Guide", "onboarding",
    "Welcome to Northwind engineering.\n\nSessions: user sessions are stored in Redis, so run a local Redis when testing auth flows.\n\nEvents: services publish domain events to Kafka. Install the Kafka CLI tools and point them at the dev cluster.\n\nCI: pushes run on GitHub Actions.",
    "auth-service", "sofia", "sofia", "2026-04-02", asserts=["C-01", "C-07", "C-04"])
doc("DOC-auth-readme", "auth-service README", "readme",
    "auth-service issues and validates access tokens.\n\nSessions are stored in Redis. Configure SESSION_REDIS_URL.\n\nAccess tokens expire after 15 minutes.",
    "auth-service", "leo", "leo", "2026-04-20", asserts=["C-01", "C-10"])
# --- stale after the CI reversal
doc("DOC-runbook-deploy", "Deploy Runbook", "runbook",
    "To deploy, trigger the Jenkins pipeline named deploy-prod. CI runs on Jenkins.\n\nRollback: re-run the previous Jenkins build.",
    "ci-pipeline", "mei", "mei", "2026-02-10", asserts=["C-03"])
# --- Kafka reversal targets (the live demo)
doc("DOC-event-bus-readme", "event-bus README", "readme",
    "event-bus is the company event backbone.\n\nThe event bus runs on Kafka. Topics follow the domain.event.v1 naming scheme.\n\nConsumers must commit offsets after processing.",
    "event-bus", "aisha", "omar", "2026-03-05", asserts=["C-07"])
doc("ADR-011", "ADR-011: Event schema registry", "adr",
    "Context: producers and consumers need shared schemas.\n\nWe adopt a schema registry. This follows the decision to use Kafka as the event bus.\n\nConsequences: schema compatibility checks run in CI.",
    "event-bus", None, "omar", "2026-03-22", cites=["D-07"])
# --- API v1 docs (stale-looking later but not claim-bound beyond the tickets)
doc("DOC-api-v1-guide", "Public API v1 Partner Guide", "readme",
    "Partners integrate with Public API v1, the supported external API.",
    "public-api-v1", "nina", "carlos", "2026-03-01", asserts=["C-05"])

# Current, correct docs and filler to reach ~40 documents.
KINDS = ["readme", "runbook", "adr", "onboarding"]
TOPICS = ["alerting", "rollback", "capacity", "oncall", "schema", "testing", "release", "security", "metrics", "backups"]
current = {"auth-service": "C-10", "billing-api": "C-11", "billing-reconciler": "C-08", "mobile-app": "C-12"}
i = 0
while doc_n + 6 < 36:
    sysid = list(SYSTEMS)[i % len(SYSTEMS)]
    contrib = SYSTEMS[sysid][3]
    who = contrib[i % len(contrib)]
    topic = TOPICS[i % len(TOPICS)]
    claim = [current[sysid]] if sysid in current and i % 3 == 0 else []
    doc(f"DOC-{sysid}-{topic}", f"{sysid} {topic} notes", KINDS[i % 4],
        f"{sysid} {topic}: how the {SYSTEMS[sysid][1]} team handles {topic} for {sysid}.\n\nKeep this page short and update it when practices change.",
        sysid, who, who, days[(i * 3) % len(days)], asserts=claim)
    i += 1
    doc_n += 1

# billing-reconciler is documented by Priya alone.
doc("DOC-reconciler-internals", "billing-reconciler internals", "readme",
    "Reconciliation runs as a nightly batch. Priya maintains the matching rules between processor payouts and ledger entries.",
    "billing-reconciler", "priya", "priya", "2026-05-01", asserts=["C-08"])

# ---------------------------------------------------------------- tickets
tk_n = 0


def ticket(title: str, status: str, sysid: str, owner: str | None, creator: str, when: str, asserts: list[str] = ()) -> str:
    global tk_n
    tk_n += 1
    tid = f"TKT-{tk_n:03d}"
    node("Ticket", tid, title=title, status=status, url=f"https://tickets.northwind.example/{tid}", created_at=ts(when))
    edge("ABOUT", ("Ticket", tid), ("System", sysid))
    edge("AUTHORED", ("Person", creator), ("Ticket", tid), ts=ts(when))
    if owner:
        edge("OWNS", ("Person", owner), ("Ticket", tid))
    for c in asserts:
        edge("ASSERTS", ("Ticket", tid), ("Claim", c))
    return tid


ticket("Add Redis cluster failover alarms for session cache", "open", "session-store", "leo", "mei", "2026-06-10", ["C-01"])
ticket("Build Kafka consumer for analytics events", "open", "event-bus", "ivan", "tomas", "2026-09-01", ["C-07"])
ticket("Build Kafka consumer for billing events", "open", "event-bus", "raj", "priya", "2026-09-05", ["C-07"])
ticket("Set up Kafka topic for legacy audit log", "closed", "event-bus", "omar", "aisha", "2026-04-10", ["C-07"])
ticket("Add pagination to v1 orders endpoint", "open", "public-api-v1", "carlos", "nina", "2026-08-25", ["C-05"])
ticket("Expose loyalty points on v1 profile endpoint", "open", "public-api-v1", "ella", "nina", "2026-09-02", ["C-05"])
ticket("Migrate staging builds off Jenkins", "closed", "ci-pipeline", "mei", "mei", "2026-06-05", ["C-03"])

TKT_TITLES = ["Investigate slow query", "Add metric for error rate", "Refactor retry logic", "Update dependency versions",
              "Write tests for edge case", "Improve logging", "Document config flags", "Clean up unused code",
              "Add alert for saturation", "Review permissions"]
while tk_n < 60:
    sysid = list(SYSTEMS)[tk_n % len(SYSTEMS)]
    contrib = SYSTEMS[sysid][3]
    who = contrib[tk_n % len(contrib)]
    status = "closed" if tk_n % 3 else "open"
    claim = [current[sysid]] if sysid in current and tk_n % 4 == 0 else []
    ticket(f"{TKT_TITLES[tk_n % len(TKT_TITLES)]} in {sysid}", status, sysid, who, contrib[0], days[(tk_n * 4) % len(days)], claim)

# ---------------------------------------------------------------- output
payload = {"nodes": nodes, "edges": edges, "supersessions": SUPERSESSIONS, "chunk_sources": CHUNK_SRC}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "northwind.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

LIVE = {
    "channel": "platform",
    "author": "aisha",
    "ts": ts("2026-10-16T09:00"),
    "text": "Heads up: from today we're dropping Kafka and moving the event bus to Redis Streams. Ops cost and on-call load are too high.",
}
(OUT / "live_reversal.json").write_text(json.dumps(LIVE, indent=1), encoding="utf-8")

counts = {k: sum(1 for n in nodes if n["label"] == k) for k in ("Person", "Doc", "Ticket", "Message", "PR", "Decision", "Claim")}
print("generated:", counts, "edges:", len(edges))
