"""MCP server: tool list, each tool's contract, and a real stdio round trip."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

import mcp_server

SERVER = str(Path(__file__).parent.parent / "mcp_server.py")


def call(name: str, **args):
    async def go():
        async with Client(mcp_server.mcp) as c:
            r = await c.call_tool(name, args)
            return r

    r = asyncio.run(go())
    assert not r.is_error, r
    sc = getattr(r, "structured_content", None)
    return sc if sc else json.loads(r.content[0].text)


TOOLS = {"ask", "why", "who_knows", "whats_stale", "as_of", "knowledge_health"}


def test_exposes_exactly_the_six_tools():
    async def go():
        async with Client(mcp_server.mcp) as c:
            return {t.name for t in (await c.list_tools()).tools}

    assert asyncio.run(go()) == TOOLS


def test_why_has_lineage_sources_and_path(svc):
    r = call("why", question="Why do we use Postgres for sessions?")
    assert r["found"] and "Postgres" in r["answer"] and "Redis" in r["answer"]
    assert any(s["id"] == "MSG-004" for s in r["sources"])
    assert any(e[1] == "SUPERSEDES" for e in r["path"]["edges"])


def test_why_says_idk_without_evidence(svc):
    r = call("why", question="Why do we use MongoDB for analytics?")
    assert not r["found"] and r["answer"].startswith("I don't know") and r["searched"]


def test_who_knows_flags_bus_factor(svc):
    r = call("who_knows", system="billing reconciler")  # free-text name resolves
    assert r["system"] == "billing-reconciler" and r["bus_factor_warning"]
    assert r["experts"][0]["name"] == "Priya Nair" and r["sources_for_top_expert"]


def test_who_knows_unknown_system_lists_choices(svc):
    r = call("who_knows", system="warp-drive")
    assert not r["found"] and "billing-reconciler" in r["systems"]


def test_as_of_time_travel(svc):
    april = call("as_of", system="session-store", date="2026-04-15")
    assert april["decision"]["id"] == "D-01" and april["later_superseded_by"][0]["id"] == "D-02"
    now = call("as_of", system="session store", date="2026-10-01")
    assert now["decision"]["id"] == "D-02" and [d["id"] for d in now["replaced"]] == ["D-01"]
    assert now["decision"]["valid_to"] is None


def test_as_of_rejects_bad_date(svc):
    async def go():
        async with Client(mcp_server.mcp) as c:
            return await c.call_tool("as_of", {"system": "session-store", "date": "last spring"})

    assert asyncio.run(go()).is_error


def test_whats_stale_for_a_decision_and_for_the_inbox(svc):
    r = call("whats_stale", decision_id="D-02")
    assert {i["item_id"] for i in r["items"]} == {"DOC-onboarding", "DOC-auth-readme", "TKT-001"}
    assert all(i["owner"] for i in r["items"])
    inbox = call("whats_stale")
    assert inbox["count"] == 0 and not inbox["found"]  # nothing awaiting approval on a fresh seed
    assert not call("whats_stale", decision_id="D-99")["found"]


def test_ask_routes_owner_and_warns_on_stale_doc(svc):
    r = call("ask", question="Who owns the deploy runbook?")
    assert r["tool"] == "owner" and "Mei Lin Chen" in r["answer"]
    assert any("Jenkins" in w and "D-04" in w for w in r["warnings"])


def test_knowledge_health_audits_existing_drift(svc):
    r = call("knowledge_health")
    assert r["stale_items"] == 7 and r["untracked_stale"] == 7 and r["health_percent"] < 100
    assert {"DOC-runbook-deploy", "DOC-onboarding", "TKT-005"} <= {d["item_id"] for d in r["drift"]}
    assert r["bus_factor"] == [{"system": "billing-reconciler", "only_expert": "Priya Nair"}]
    assert [u["id"] for u in r["unowned"]] == ["ADR-011"]


def test_stdio_round_trip():
    """Launch the server exactly as Claude Desktop would and call a tool through the real transport."""
    async def go():
        params = StdioServerParameters(command=sys.executable, args=[SERVER])
        async with Client(params) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            res = await c.call_tool("who_knows", {"system": "billing-reconciler"})
            return tools, res

    tools, res = asyncio.run(go())
    assert tools == TOOLS and not res.is_error
