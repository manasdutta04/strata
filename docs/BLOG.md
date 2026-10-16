# Your company's knowledge doesn't go missing. It goes wrong.

*How we built Strata, a company brain on FalkorDB that notices when a document has become false, for Graph Hacks.*

> Links to add before publishing: demo video · repo · live demo (or local setup). The demo company in this post is fictional and synthetic.

---

## The failure nobody searches for

Picture a Tuesday. In `#platform`, a lead writes:

> Decision: sessions move from Redis to Postgres. Cost and durability. ADR-004 is superseded, migration starts Monday.

Good decision, clearly stated, and it will be lost within a week. The onboarding guide still says *"user sessions are stored in Redis, so run a local Redis when testing auth flows."* The `auth-service` README says the same. An open ticket is still building Redis failover alarms. A new engineer follows the guide on Monday.

None of this is a search problem. Every one of those documents is easy to find. The problem is that **nothing knows they are now wrong**. A search index stores what documents say. It has no concept of *what the company currently believes*, so it cannot tell you which documents disagree with it.

Strata is our attempt at the missing piece: a company brain that keeps every decision as a layer, knows which layer is current, and tells you, with a graph path as proof, which docs and tickets just became stale and who owns them.

The name is literal. Rock strata are layers: older ones get buried by newer ones but are never erased. Strata (the product) never deletes a decision. It closes it.

## The model: facts that expire, documents that assert them

The whole product is a small idea expressed as a graph. Decisions *establish* claims. Documents and tickets *assert* those claims or *cite* the decisions. Every decision and claim has a validity window.

```
(Decision)-[:ESTABLISHES]->(Claim)
(Doc | Ticket)-[:ASSERTS]->(Claim)
(Doc | Ticket)-[:CITES]->(Decision)
(Decision)-[:SUPERSEDES]->(Decision)
```

Time is a convention, not a feature: every timestamp is epoch milliseconds, and `valid_to` unset means "currently in force". "As of time T" is always `valid_from <= T AND (valid_to IS NULL OR valid_to > T)`.

When a decision is reversed, we close the old one. We never delete anything:

```cypher
MATCH (new:Decision {id: $new_id}), (old:Decision {id: $old_id})
SET old.valid_to = new.valid_from
MERGE (new)-[:SUPERSEDES {ts: new.valid_from}]->(old)
WITH old, new
OPTIONAL MATCH (old)-[:ESTABLISHES]->(c:Claim) WHERE c.valid_to IS NULL
SET c.valid_to = new.valid_from
RETURN old.id AS old_id, new.id AS new_id, collect(c.id) AS closed_claims
```

And now "what is stale?" is a single traversal. Anything that asserts a claim we just closed, or cites the decision we just superseded:

```cypher
MATCH (new:Decision {id: $new_id})-[:SUPERSEDES]->(old:Decision)
MATCH (item)-[r:ASSERTS|CITES]->(x)
WHERE (x = old OR (old)-[:ESTABLISHES]->(x)) AND NOT (item)-[:NEXT_VERSION]->()
  AND (item:Doc OR (item:Ticket AND item.status = 'open'))
RETURN DISTINCT item.id AS item_id, labels(item)[0] AS item_label, item.title AS title,
       type(r) AS how, x.id AS stale_id, coalesce(x.text, x.summary) AS stale_text
```

That query is the product. There is no keyword matching, no similarity threshold, no model deciding whether a doc "seems outdated". A doc is stale because there is an edge from it to a fact that is no longer true, and the edge is the explanation we show the user.

## The demo: one Slack message

Our synthetic company, Northwind Labs, has 25 people, 5 teams, 8 systems, about 40 docs, 60 tickets and 270 messages, generated deterministically from a written storyline so every demo beat is reproducible.

Then we paste a message that is *not* in the seed data:

> Heads up: from today we're dropping Kafka and moving the event bus to Redis Streams. Ops cost and on-call load are too high.

What happens next, all through the real pipeline:

1. **Ingestor** extracts a structured decision. Crucially, the model is shown the decisions currently in force and must choose which one this supersedes *from that list*. It cannot invent an id. Here it picks the Kafka decision.
2. The `supersede` query above closes the Kafka decision and its claim.
3. **Steward** runs the staleness query. Result: exactly **3 docs and 2 open tickets**. The event-bus README, the onboarding guide, an ADR that cites the Kafka decision, and two tickets building Kafka consumers. (A closed ticket that also mentions Kafka is correctly ignored.)
4. Every item gets an owner. Four have a direct owner. The ADR has none, so Strata routes it through the team that owns the system it's about and picks the member with the highest expertise on that system.
5. For each item the model drafts a minimal diff: a `- ` line and a `+ ` line, nothing else.

Then the part we care most about: **nothing changes without a click.** Each fix is an open task. Approve creates a *new version* of the doc linked by `NEXT_VERSION`; the old version stays in the graph. Reject leaves the item flagged. The human gate isn't a feature bolted on at the end; it's what makes it safe to let an automated system accuse your documentation of being wrong.

## "Why?" is a graph path, and so is time travel

Ask *"Why do we use Postgres for sessions?"* and the answer is built from one query that returns the decision in force, who made it, the chain of decisions it replaced, and the evidence. In the UI the exact path is highlighted: the new decision, a dashed `SUPERSEDES` edge to the old one, the Slack messages that evidence each. Every sentence of the answer carries the ids of its sources, and you can click through to them.

Because nothing is deleted, time travel costs nothing. The slider on the graph re-runs the **same query** with a different `$t`. Drag back to April and *"Why is the event bus on Kafka?"* answers with the Kafka decision and adds that it was later superseded. Drag forward and it's Redis Streams. Closed decisions dim; they don't vanish.

And when the graph has nothing, Strata says **"I don't know"** and shows what it searched. We spent more design effort on that behavior than on any happy path. A company brain that confidently invents a decision rationale is worse than no brain.

## Who actually knows? Ask the algorithms

The org chart says who *owns* a system. It doesn't say who *understands* it. Strata derives symmetric `COLLABORATES` edges (both directions, since the algorithms treat edges as directed) from shared authored and reviewed work, then runs FalkorDB's graph algorithms over them:

```cypher
CALL algo.pageRank('Person', 'COLLABORATES') YIELD node, score
CALL algo.betweenness({nodeLabels: ['Person'], relationshipTypes: ['COLLABORATES']}) YIELD node, score
CALL algo.labelPropagation({nodeLabels: ['Person'], relationshipTypes: ['COLLABORATES']}) YIELD node, communityId
```

A person's expertise on a system is their normalised activity there times `(1 + PageRank)`. Betweenness drives a "knowledge bridge" badge: in the demo data, one data engineer reviews PRs across Payments, Growth and Data and lights up as the connection between teams. Label propagation finds an informal team (two Growth engineers and one Mobile engineer who work together far more than with their own teams), which the org chart doesn't show.

Bus factor is a plain aggregation: systems where at most one person has meaningful authored/reviewed activity. In the seed data exactly one system, `billing-reconciler`, trips it, and the Who Knows card shows the warning next to the one person who holds it.

## Agents that only talk through the graph

Ingestor, Steward and Concierge never call each other. They share state through `Task` nodes and `HANDED_TO` edges:

```
(Ingestor)-[:CREATED]->(Task {status: 'in_progress'})
(Task)-[:HANDED_TO {ts}]->(Steward)  ->  (Concierge)  ->  status 'done'
```

Every step persists before the next begins, and the Steward is idempotent (it skips items that already have a task), so an interrupted run can be finished by `resume` from task status alone. We test it: set a finished run back to `in_progress`, call `resume`, and the run is finished from graph state alone. Personal memory works the same way. Each user gets their own FalkorDB graph recording sessions, questions and which decision version they were shown, and on the next session we compare against what's in force now: *"Since you last asked about the event bus, that decision changed."*

## Where an LLM is (and isn't) allowed

This was the design rule that shaped everything: **the LLM never writes Cypher and never writes an answer.**

- It extracts a decision from a message, grounded in a list of real decisions.
- It drafts the diff text for a fix.
- As a fallback, when intent is genuinely unclear, it picks one tool from a short vetted list.

Staleness, supersession, ownership, expertise, lineage and the *text* of every answer come from queries. Answers are composed from graph results so each sentence can point at its evidence. The side effect we didn't expect: the product became fast and stable. Graph-backed answers return in a few hundredths of a second; only the extraction and drafting calls touch a model.

## Things that went wrong, and what we fixed

We would rather tell you than let you find them.

- **Our bus-factor system flagged nothing at first.** Counting every message about a system inflated the secondary people's activity past the threshold. Fixing the *data* (the storyline says one person truly knows the reconciler) was right; the query stayed as written.
- **The memory banner would have lied after a reset.** Resetting the demo reseeded the company graph but left old per-user graphs behind, so a user could be told a decision "changed" when it hadn't. We caught it while polishing; reset now clears them.
- **Time-travel views would have polluted memory.** Asking *"as of April"* recorded the old decision as "seen," so the next session would have claimed it had changed. Historical views and slider re-runs are now deliberately not remembered.
- **We deleted a query nobody used.** A full-text lookup survived from the first sketch. If the README lists every query the product depends on, every listed query had better be used.

## Honest limits

- The company is **synthetic**. Northwind Labs is fictional and labelled as such in the UI; it's generated from a fixed seed. We did not test on real company data.
- We run the language model through the local Claude Code CLI (no API key), which is why the AI path is not available on a hosted deployment. Responses are cached by prompt hash so recordings are reproducible; a cached run is a replay of a real earlier response, not a live call, and we say so in the README. A first uncached run of the live reversal takes about 20 seconds.
- Retrieval-based topic matching uses a distance threshold tuned on the demo corpus. Expertise scores count all authored/reviewed items on a system, including messages and tickets.
- AI coding assistants were used throughout development, and disclosed in the README. The design, graph model and queries are ours to explain; the test suite (16 tests, including the exact "3 docs and 2 tickets with owners" contract) is how we keep ourselves honest.

## Why FalkorDB

Remove it and the product doesn't degrade; it ceases to exist. Supersession and as-of answers, staleness, ownership routing, PageRank/betweenness/label-propagation expertise, bus factor, provenance paths, agent hand-offs and per-user memory are all graph queries or graph algorithms. FalkorDB's ability to hold many isolated graphs made per-user memory a one-line decision (`strata_user_<id>`), and having vector search and graph algorithms in the same engine as the traversals meant one system answered "which chunk is relevant?", "which decision does it concern?" and "who knows it?" without glue.

## Try it

Run the stack with Docker and two commands (the README has the exact steps), ask *"Why do we use Postgres for sessions?"*, then paste the Kafka → Redis Streams message and watch five stale items light up. Then drag the slider and watch the answer change its mind.

Company knowledge will always drift. The goal isn't to stop it. It's to **notice**, name an owner, and keep the layers underneath so you can always dig down and see what was true at any point.
