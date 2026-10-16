"""The only module that talks to FalkorDB. Every query is a named template in queries/*.cypher."""
from pathlib import Path
from typing import Any

from falkordb import FalkorDB, Graph

from config import settings

QUERY_DIR = Path(__file__).parent / "queries"


class GraphService:
    def __init__(self, graph_name: str = "strata") -> None:
        self.db = FalkorDB(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            username=settings.falkordb_username or None,
            password=settings.falkordb_password or None,
        )
        self.name = graph_name
        self.graph: Graph = self.db.select_graph(graph_name)
        self._templates: dict[str, str] = {}

    def template(self, name: str) -> str:
        if name not in self._templates:
            self._templates[name] = (QUERY_DIR / f"{name}.cypher").read_text(encoding="utf-8")
        return self._templates[name]

    def run(self, name: str, **params: Any) -> list[dict[str, Any]]:
        """Run a named template; return rows as dicts keyed by RETURN column."""
        res = self.graph.query(self.template(name), params)
        cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
        return [dict(zip(cols, row)) for row in res.result_set]

    def raw(self, cypher: str, params: dict[str, Any] | None = None):
        """Escape hatch for schema DDL and seeding only; never exposed to the LLM."""
        return self.graph.query(cypher, params or {})

    def reset(self) -> None:
        try:
            self.graph.delete()
        except Exception:  # noqa: BLE001
            pass
        self.graph = self.db.select_graph(self.name)
