"""Router wiring: Rapfi path sets engine='rapfi'; fallback sets
'python-fallback'. Availability/compute are monkeypatched so tests are
deterministic and never touch a real Rapfi binary.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.gomoku_ai import rapfi, router as gomoku_router
from rt_backend.gomoku_ai.rapfi import RapfiMove
from rt_backend.gomoku_ai.router import build_router

EMPTY = [[0] * 15 for _ in range(15)]


async def _avail_true() -> bool:
    return True


async def _avail_false() -> bool:
    return False


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(build_router())
    return TestClient(app)


def _board_with_one_stone():
    b = [row[:] for row in EMPTY]
    b[7][7] = 1
    return b


def test_rapfi_path_sets_engine_label(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def fake_compute(board, to_move, *, timeout_s):
        return RapfiMove(row=7, col=8, score=0, winning=False, blocks=False)

    monkeypatch.setattr(gomoku_router, "compute_move", fake_compute)
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 3},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["engine"] == "rapfi"
    assert (j["best"]["row"], j["best"]["col"]) == (7, 8)
    assert len(j["top_moves"]) == 3
    assert all((m["row"], m["col"]) == (7, 8) for m in j["top_moves"])


def test_fallback_when_rapfi_unavailable(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_false)
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 3},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["engine"] == "python-fallback"
    assert 0 <= j["best"]["row"] < 15


def test_fallback_when_rapfi_raises(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def boom(board, to_move, *, timeout_s):
        raise rapfi.RapfiUnavailable("simulated")

    monkeypatch.setattr(gomoku_router, "compute_move", boom)
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 1},
    )
    assert r.status_code == 200
    assert r.json()["engine"] == "python-fallback"


def test_strength_maps_to_timeout(client, monkeypatch):
    """Each strength tier must give Rapfi a proportional subprocess timeout
    (time_turn/1000 + 3s slack)."""
    seen = {}
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def capture(board, to_move, *, timeout_s):
        seen["t"] = timeout_s
        return RapfiMove(row=7, col=8, score=0, winning=False, blocks=False)

    monkeypatch.setattr(gomoku_router, "compute_move", capture)
    client.post(
        "/api/gomoku/next-move",
        json={"board": _board_with_one_stone(), "to_move": 2, "strength": 3, "top_k": 1},
    )
    # strong: 5s + 3s slack = 8s
    assert seen["t"] == 8.0
