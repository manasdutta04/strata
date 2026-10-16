# Demo video: shooting script, labels and checklist

Target length **3:30–3:50** (hard limit 4:00). 1080p, 60 fps if possible, cursor visible, captions on, no dead air.
The video must show every Company Brain focus point **by name on screen**. Each beat below lists its label.

Everything in the video is the real running product against the synthetic Northwind Labs graph. Do not narrate anything the screen does not show.

---

## Before you record

### Terminal 1: database and servers

```bash
docker compose up -d                                   # Docker Desktop must be running first
cd backend && source .venv/bin/activate                # Windows: .venv\Scripts\activate
uvicorn app.main:app --port 8000
```

```bash
cd web && npm run dev                                  # http://localhost:3000
```

### Terminal 2: warm up (run this every time right before a take)

```bash
cd backend && python demo_warmup.py
```

It reseeds the graph, checks the five golden questions (< 3 s each), runs the live Kafka → Redis Streams reversal through the real pipeline so every LLM response is cached, asserts **exactly 3 docs + 2 tickets with owners and drafts**, then resets to a clean slate (empty inbox, no personal memory). It must end with `READY to record.` Do not record if it does not.

### Checklist

- [ ] `demo_warmup.py` says **READY to record.**
- [ ] Browser at 1920×1080, zoom 100 %, bookmarks bar hidden, notifications off, one clean window. Open `http://localhost:3000`. Page fully loaded, graph settled.
- [ ] The Memory banner is **not** showing (clean slate). If it is, press **Reset demo**.
- [ ] Second tab: `http://localhost:3100` (FalkorDB Browser), graph `strata` selected. Third tab: the repo README, scrolled to *Graph data model*.
- [ ] Editor window ready with `backend/graph/queries/pagerank.cypher` and `betweenness.cypher`.
- [ ] Two title cards made in any editor (text below). Export as 1920×1080 PNG.
- [ ] No console errors (DevTools closed during the take). System notifications and chat apps closed.
- [ ] Mic checked. Screen recorder set to 1080p. Cursor highlight on if available.
- [ ] Do one **full rehearsal** without recording; note any beat that runs long.

### Title cards (beat 1)

**Card A (left):** *Engineering Onboarding Guide.* "Sessions: user sessions are stored in Redis, so run a local Redis when testing auth flows."
**Card B (right):** *#platform, Aug 14.* "Decision: sessions move from Redis to Postgres. Cost and durability. ADR-004 is superseded, migration starts Monday."
These are verbatim from the seed data, so they match what the product shows later.

---

## Shooting script

| Time | Beat | On screen | Say (voice-over) | Label (lower-third) |
|---|---|---|---|---|
| **0:00–0:20** | The problem | Cards A and B side by side, then the Strata logo | "Company knowledge doesn't just go missing. It goes wrong. A decision gets reversed in Slack, and the onboarding doc, the README and three tickets still say the old thing. Search finds documents. Nothing notices when one has become wrong. This is Strata." | *Strata: the company brain that knows when it's wrong* |
| **0:20–1:10** | **Ask Why** | Click **Why do we use Postgres for sessions?** → answer appears; graph zooms to the path (new decision → dashed *supersedes* → old decision, evidence, person). Click citation **[1]**: the source card shows the Slack message. Click **Why did we use Redis for sessions? (as of April)** → "later superseded". Type **Why do we use MongoDB for analytics?** → "I don't know" with *What I searched*. Finally click **Why is the event bus on Kafka?** (sets up the memory beat; leave it as the last question) | "Ask why, and Strata gives the decision in force, who made it, what it replaced, and the original evidence. This is the graph path it used, highlighted. Every sentence cites its source: this is the actual Slack message. As of April, the answer was Redis, and it tells you that was later superseded. And when the graph has no evidence, it says I don't know and shows what it searched. It never invents." | *Tracing decisions back to their source* · *Answers with clear sources* |
| **1:10–1:40** | **Who Knows** | **Who Knows** tab. System is `billing-reconciler`: bus-factor banner, Priya first, score bars (activity, PageRank, betweenness). Click **Who connects Payments and Data?** in chat → Tomás. Cut to the editor: `pagerank.cypher`, `betweenness.cypher` (2 s each) | "Who actually knows the billing reconciler? Not the org chart: activity, scored with FalkorDB's PageRank and betweenness over who collaborates with whom. One person understands it, so there's a bus-factor warning. And Tomás is the knowledge bridge between Payments and Data. Here is the algorithm query behind it." | *Who owns what, and who knows what* |
| **1:40–2:40** | **The wow: live drift** | **Drift Inbox** tab. Click *use the live example*, then **Ingest**. The stepper runs Ingestor → Steward → Concierge. Result line: closes `D-07` (kept, not deleted), **3 docs + 2 tickets** stale. Scroll the inbox: five cards, each with owner, *why stale* path and a diff. Click the **ADR-011** card: graph highlights its path to the closed claim. Point at its owner: Omar, routed through the Platform team because the ADR has no direct owner. **Approve** `event-bus README`: card turns *approved*, "new version created, the old version is kept". Click **Reject** on one ticket. Drag the **time slider** back to April → the event-bus answer re-runs and shows **Kafka**, "later superseded"; drag it back to *Now* → **Redis Streams**, replaced Kafka | "Now the part that matters. Someone announces we're dropping Kafka for Redis Streams. I paste that message in. Strata extracts the decision, closes the old one without deleting it, and walks the graph: three docs and two open tickets just became wrong. Every one has an accountable owner. This ADR had none, so Strata routed it through the team and expertise. It drafts the fix as a diff, but nothing changes without a human. I approve this one, reject that one. Now drag back in time: the answer is Kafka, marked as later superseded. Drag forward: Redis Streams. Same query, different timestamp." | *Keeping knowledge current as things change* |
| **2:40–3:15** | Memory and coordination | **Reload the page** → Memory banner: "Since you last asked 'Why is the event bus on Kafka?', that decision changed on …". Open the **Agents** tab: the run with `created Ingestor → handed to Steward → handed to Concierge`, plus the count of drift tasks. | "Reload, and it remembers me: since I last asked about the event bus, that decision changed. That's a per-user memory graph in FalkorDB. And these three agents never talk to each other directly. They share state only through task nodes in the graph, so the hand-off is right here, and a run interrupted by a restart resumes from task status." | *Remember across sessions* · *Share state between agents* |
| **3:15–3:45** | Proof the graph is load-bearing | README data model section (nodes, relationships, temporal convention) → the list of Cypher queries (scroll quickly) → FalkorDB Browser: run `MATCH p=(d:Decision)-[:SUPERSEDES*]->(o:Decision) RETURN p` and show the lineage | "The model: decisions, claims, docs, tickets, people, and tasks in one graph, with time on every fact. Every query and algorithm is listed in the README. Remove FalkorDB and every feature you just saw disappears: the lineage, the staleness, the ownership, the expertise, the memory, and the agent hand-offs." | *Knowledge from docs, tickets, and chats in one graph* |
| **3:45–3:50** | End card | Strata logo, repo URL, **Tracks: Company Brain · Agent Memory and Coordination** | "Strata. Built on FalkorDB." | |

Rough budget: 20 + 50 + 30 + 60 + 35 + 30 + 5 = 3:50. If a rehearsal runs over, cut in this order: the MongoDB "I don't know" (keep it if you can; it is the strongest trust beat), the Reject click, the algorithm editor cutaway.

### Honesty lines (say or caption at least one)

- On beat 1:40, caption or say: *"Demo data is synthetic: a fictional 25-person company."* (also shown in the UI header).
- The warm cache makes ingest finish in about a second. Do not say "the model answers instantly". If you mention speed, say "Strata runs the real extraction pipeline; on a first run the model takes about 20 seconds, and this recording replays a cached response." The README discloses this.
- The graph path, owners, stale items and answer text come from graph queries; the LLM only extracts the decision and drafts the diff text.

---

## Recording tips

- Record each beat as a separate clip, then cut together. Rerun `demo_warmup.py` (or press **Reset demo**) before any beat that needs a clean inbox, and always before re-recording beat 1:40 onward.
- Order matters for the memory beat: *Why is the event bus on Kafka?* must be asked (typed or clicked) **before** the ingest, and must **not** be asked again before you reload. Use the slider, not a new question, to show the flip: slider re-runs and "as of <past>" questions are deliberately not remembered, so the banner still reports the change.
- Move the cursor deliberately and pause 1 s on anything you want read (a citation, the diff, the owner).
- Add captions (burned in). Keep text on screen long enough to read twice.
- Export 1080p MP4; keep it under the platform's size limit; upload and link it in the README.

### GIF for the top of the README

Cut 10–15 seconds of the ingest → inbox lights up → approve moment from your recording (about 1:45–2:10), then:

```bash
ffmpeg -ss 00:01:45 -t 12 -i demo.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" docs/live-drift.gif
```

Then replace the `<!-- GIF ... -->` comment at the top of `README.md` with `![Live drift](docs/live-drift.gif)` and fill in the video, demo and blog links.

### If something goes wrong mid-take

| Problem | Fix |
|---|---|
| Inbox shows leftover items or the Memory banner appears unexpectedly | Press **Reset demo** (top right) or rerun `demo_warmup.py`, reload, retake |
| "backend offline" overlay | Start `uvicorn` (Terminal 1); the page recovers on its own within 5 s |
| FalkorDB unreachable | Start Docker Desktop, then `docker compose up -d` |
| Ingest takes ~20 s | The LLM cache was cold. Let it finish once, then reset and retake |
| Slider re-ask doesn't fire | It re-asks the **last why question** after ~0.5 s; ask the event-bus question first |
| Memory banner missing after reload | You asked the event-bus question again after the ingest (that records the new decision as seen). Reset and retake |
| Memory banner also lists session storage | You asked the Postgres question after ingesting something that changed it; reset and retake |

---

## Pre-submission checklist (video, README, repo)

- [ ] Video uploaded and public; link added to README and the submission form
- [ ] GIF added to the top of the README
- [ ] README links filled: live demo (or complete local setup, already present), video, blog
- [ ] Repo is public; `.env`, `.llm_cache`, `node_modules` are not committed (`git status` clean)
- [ ] Fresh-clone test: follow the README setup from scratch, run `pytest`, run the demo once
- [ ] Both tracks named at submission: **Company Brain** and **Agent Memory and Coordination**
- [ ] AI-assistance disclosure present in the README
- [ ] Submit with margin before the deadline
