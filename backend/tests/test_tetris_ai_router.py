"""Tests for the Tetris AI HTTP router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.tetris_ai.router import build_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_router())
    return TestClient(app)


# --------------------------------------------------------------------------
# /api/tetris/pieces
# --------------------------------------------------------------------------

def test_pieces_lists_all_seven(client):
    r = client.get("/api/tetris/pieces")
    assert r.status_code == 200
    assert sorted(r.json()["pieces"]) == ["I", "J", "L", "O", "S", "T", "Z"]


# --------------------------------------------------------------------------
# /api/tetris/next-move
# --------------------------------------------------------------------------

def test_next_move_returns_rotation_target_x_and_moves(client):
    # Empty 10x20 board, I piece. The bot should bottom out.
    body = {
        "board": ["." * 10] * 20,
        "piece": "I",
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    j = r.json()
    assert set(j) >= {
        "rotation", "target_x", "final_y", "moves", "score",
        "cleared_lines", "lookahead", "metrics", "elapsed_ms",
    }
    assert j["moves"][-1] == "hard_drop"
    assert j["lookahead"] is False
    assert j["cleared_lines"] == 0


def test_next_move_with_next_piece_enables_lookahead(client):
    body = {
        "board": ["." * 10] * 20,
        "piece": "O",
        "next_piece": "I",
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    assert r.json()["lookahead"] is True


def test_next_move_solves_the_four_row_vertical_i_well(client):
    # A classic 4-row well at column 9; the I must be placed vertically there.
    board = ["." * 10] * 16 + ["#########."] * 4
    body = {"board": board, "piece": "I", "next_piece": "O", "current_x": 3}
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["rotation"] == 1  # vertical
    assert j["target_x"] == 9
    assert j["cleared_lines"] == 4
    # The move sequence must end with a hard drop after rotating once.
    assert j["moves"] == ["rotate", "right", "right", "right", "right", "right", "right", "hard_drop"]


def test_next_move_accepts_int_rows_and_lowercase_piece(client):
    body = {
        "board": [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "..##......",
        ],
        "piece": "t",
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    assert r.json()["piece" if False else "target_x"] >= 0  # schema key sanity


def test_next_move_rejects_ragged_board(client):
    body = {"board": [".....", "...."], "piece": "O"}
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 422
    assert "长度" in r.json()["detail"]


def test_next_move_rejects_unknown_piece(client):
    body = {"board": ["." * 10] * 20, "piece": "X"}
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 422


def test_next_move_returns_409_when_board_is_full(client):
    body = {"board": ["##########"] * 20, "piece": "T"}
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 409
    assert "游戏已结束" in r.json()["detail"]


def test_next_move_rejects_current_x_outside_board(client):
    body = {
        "board": ["." * 10] * 20,
        "piece": "O",
        "current_x": 42,
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 422


def test_next_move_emits_rotate_left_right_in_that_order(client):
    body = {
        "board": ["." * 10] * 20,
        "piece": "T",
        "current_x": 3,
        "current_rotation": 0,
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    moves = r.json()["moves"]
    assert moves[-1] == "hard_drop"
    # Rotations come first, then horizontals.
    for tok in ("left", "right"):
        if tok in moves:
            assert "rotate" not in moves[moves.index(tok) + 1 :]
    # The number of left/right moves matches the column delta from the I-spawn
    # position (current_x is used as the known start, so it must match).
    lefts = moves.count("left")
    rights = moves.count("right")
    assert 3 - lefts + rights == r.json()["target_x"]


def test_next_move_respects_custom_weights(client):
    body = {
        "board": ["." * 10] * 20,
        "piece": "I",
        "weights": {
            "landing_height": 100.0,  # reward tall placements
            "eroded_piece_cells": 0.0,
            "row_transitions": 0.0,
            "column_transitions": 0.0,
            "holes": 0.0,
            "wells": 0.0,
        },
    }
    r = client.post("/api/tetris/next-move", json=body)
    assert r.status_code == 200
    # The I should now prefer the top of the board over the floor.
    assert r.json()["final_y"] <= 16
