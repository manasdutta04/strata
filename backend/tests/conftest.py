import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.service import GraphService  # noqa: E402
from seed import load  # noqa: E402


@pytest.fixture(scope="module")
def svc():
    s = GraphService()
    load(s)
    return s


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: calls the LLM (cached in .llm_cache); skipped when STRATA_SKIP_LLM=1, e.g. in CI")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("STRATA_SKIP_LLM") == "1":
        skip = pytest.mark.skip(reason="needs an LLM (STRATA_SKIP_LLM=1)")
        for item in items:
            if "llm" in item.keywords:
                item.add_marker(skip)
