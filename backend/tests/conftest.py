import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.service import GraphService  # noqa: E402
from seed import load  # noqa: E402


@pytest.fixture(scope="session")
def svc():
    s = GraphService()
    load(s)
    return s
