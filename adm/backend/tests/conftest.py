import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _forget_down_sites():
    """The gate remembers dead sites across runs; tests must not inherit that."""
    from core import proxima_client
    proxima_client._recently_down.clear()
    yield
    proxima_client._recently_down.clear()
