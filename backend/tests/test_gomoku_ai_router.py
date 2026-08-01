"""Tests for the Gomoku AI HTTP router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.gomoku_ai.router import build_router

EMPTY = [[0] * 15 for _ in range(15)]


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_router())
    return TestClient(app)


# --------------------------------------------------------------------------
# /api/gomoku/next-move
# --------------------------------------------------------------------------

def test_next_move_on_empty_board_returns_center(client):
    r = client.post("/api/gomoku/next-move", json={"board": EMPTY, "to_move": 1})
    assert r.status_code == 200
    j = r.json()
    assert j["best"]["row"] == 7
    assert j["best"]["col"] == 7
    assert j["best"]["winning"] is False
    assert len(j["top_moves"]) == 3
    assert "elapsed_ms" in j


def test_next_move_works_for_white_too(client):
    r = client.post("/api/gomoku/next-move", json={"board": EMPTY, "to_move": 2})
    assert r.status_code == 200
    assert r.json()["best"]["row"] == 7


def test_next_move_takes_immediate_win(client):
    board = [row[:] for row in EMPTY]
    for c in range(5, 9):
        board[7][c] = 1
    r = client.post("/api/gomoku/next-move", json={"board": board, "to_move": 1})
    assert r.status_code == 200
    j = r.json()
    assert j["best"]["winning"] is True
    # The move closes a 4-in-a-row at row 7
    assert j["best"]["row"] == 7
    assert j["best"]["col"] in (4, 9)


def test_next_move_blocks_opponent_four(client):
    board = [row[:] for row in EMPTY]
    for c in range(5, 9):
        board[7][c] = 2
    r = client.post("/api/gomoku/next-move", json={"board": board, "to_move": 1})
    assert r.status_code == 200
    j = r.json()
    assert j["best"]["blocks"] is True
    assert (j["best"]["row"], j["best"]["col"]) in {(7, 4), (7, 9)}


def test_next_move_rejects_wrong_board_size(client):
    r = client.post("/api/gomoku/next-move", json={"board": [[0] * 10] * 10, "to_move": 1})
    assert r.status_code == 422
    assert "15" in r.json()["detail"]


def test_next_move_rejects_invalid_cell(client):
    bad = [row[:] for row in EMPTY]
    bad[0][0] = 5
    r = client.post("/api/gomoku/next-move", json={"board": bad, "to_move": 1})
    assert r.status_code == 422
    assert "合法值" in r.json()["detail"]


def test_next_move_rejects_ragged_board(client):
    bad = [row[:] for row in EMPTY]
    bad[0] = bad[0][:10]
    r = client.post("/api/gomoku/next-move", json={"board": bad, "to_move": 1})
    assert r.status_code == 422


def test_next_move_respects_top_k(client):
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": EMPTY, "to_move": 1, "top_k": 5},
    )
    assert r.status_code == 200
    # Empty board has one legal move (center); the response pads to top_k
    # so the client always sees a stable array shape.
    assert len(r.json()["top_moves"]) == 5
    assert all(m["row"] == 7 and m["col"] == 7 for m in r.json()["top_moves"])


def test_next_move_rejects_invalid_top_k(client):
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": EMPTY, "to_move": 1, "top_k": 10},
    )
    assert r.status_code == 422


def test_next_move_rejects_invalid_to_move(client):
    r = client.post("/api/gomoku/next-move", json={"board": EMPTY, "to_move": 3})
    # Pydantic Literal validation rejects this
    assert r.status_code == 422


def test_next_move_rejects_invalid_strength(client):
    r = client.post(
        "/api/gomoku/next-move",
        json={"board": EMPTY, "to_move": 1, "strength": 9},
    )
    assert r.status_code == 422
    assert "strength" in r.json()["detail"]


def test_next_move_accepts_all_strength_tiers(client):
    """All three strength tiers must return 200 with a valid best move."""
    board = [row[:] for row in EMPTY]
    board[7][7] = 1  # one black stone so it's not the empty-board shortcut
    for s in (1, 2, 3):
        r = client.post(
            "/api/gomoku/next-move",
            json={"board": board, "to_move": 2, "strength": s, "top_k": 1},
        )
        assert r.status_code == 200
        j = r.json()
        assert 0 <= j["best"]["row"] < 15
        assert 0 <= j["best"]["col"] < 15
