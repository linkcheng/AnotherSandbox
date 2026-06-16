"""cap-terminal pytest fixtures。"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    """加载 FastAPI app 并返回 TestClient。"""
    from cap_terminal.main import app

    with TestClient(app) as c:
        yield c
