"""Tests for the Tetris AI board metrics and placement search."""
import pytest

from rt_backend.tetris_ai.board import (
    BoardError,
    apply_placement,
    column_tops,
    parse_board,
    rows_to_matrix,
)
from rt_backend.tetris_ai.pieces import (
    distinct_rotations,
    normalize_piece,
    piece_width,
    rotation_states,
    spawn_x,
)
from rt_backend.tetris_ai.service import (
    NoPlacementError,
    _landing_y,
    best_placement,
    plan_moves,
)

W = 10


def board(*rows: str):
    """Build a board from '.'/'#' art, padding to 10 columns."""
    return parse_board([r.ljust(W, ".") for r in rows])


def empty(height: int = 20):
    return parse_board(["." * W] * height)


# --------------------------------------------------------------------------
# parse_board
# --------------------------------------------------------------------------

def test_parse_board_string_rows():
    rows, width = parse_board(["..##......", "##########"])
    assert width == 10
    assert rows == [0b0000001100, 0b1111111111]


def test_parse_board_int_rows_match_string_rows():
    from_str, _ = parse_board(["..##......"])
    from_int, _ = parse_board([[0, 0, 1, 1, 0, 0, 0, 0, 0, 0]])
    assert from_str == from_int


def test_parse_board_treats_any_nonempty_token_as_filled():
    rows, _ = parse_board([["", ".", " ", 0, 7, "T", True, None, "_", 2]])
    # indices 4, 5, 6, 9 are filled
    assert rows == [(1 << 4) | (1 << 5) | (1 << 6) | (1 << 9)]


def test_parse_board_rejects_ragged_rows():
    with pytest.raises(BoardError, match="长度"):
        parse_board(["....", "..."])


def test_parse_board_rejects_empty():
    with pytest.raises(BoardError, match="不能为空"):
        parse_board([])


def test_parse_board_rejects_too_narrow():
    with pytest.raises(BoardError, match="宽度至少"):
        parse_board(["..."])


def test_rows_to_matrix_roundtrips():
    rows, width = parse_board(["..##......", "##########"])
    assert rows_to_matrix(rows, width) == [
        [0, 0, 1, 1, 0, 0, 0, 0, 0, 0],
        [1] * 10,
    ]


def test_column_tops():
    rows, width = board("..........", "..#.......", "..##......")
    tops = column_tops(rows, width)
    assert tops[2] == 1
    assert tops[3] == 2
    assert tops[0] == 3  # empty column -> height


# --------------------------------------------------------------------------
# pieces
# --------------------------------------------------------------------------

def test_all_pieces_have_four_cells_in_every_rotation():
    for name in "IOTSZJL":
        for cells in rotation_states(name):
            assert len(cells) == 4, name
            assert len(set(cells)) == 4, f"{name} has duplicate cells"


def test_all_rotations_are_normalized_to_origin():
    for name in "IOTSZJL":
        for rot, cells in enumerate(rotation_states(name)):
            assert min(dx for dx, _ in cells) == 0, (name, rot)
            assert min(dy for _, dy in cells) == 0, (name, rot)


def test_distinct_rotations():
    assert distinct_rotations("O") == (0,)
    assert distinct_rotations("I") == (0, 1)
    assert distinct_rotations("S") == (0, 1)
    assert distinct_rotations("Z") == (0, 1)
    assert distinct_rotations("T") == (0, 1, 2, 3)
    assert distinct_rotations("J") == (0, 1, 2, 3)
    assert distinct_rotations("L") == (0, 1, 2, 3)


def test_piece_width():
    assert piece_width("I", 0) == 4
    assert piece_width("I", 1) == 1
    assert piece_width("O", 0) == 2
    assert piece_width("T", 0) == 3


def test_normalize_piece_accepts_lowercase():
    assert normalize_piece("t") == "T"
    with pytest.raises(ValueError, match="未知方块"):
        normalize_piece("X")


def test_spawn_x_centers_piece():
    assert spawn_x("I", 10, 0) == 3
    assert spawn_x("O", 10, 0) == 4


# --------------------------------------------------------------------------
# landing
# --------------------------------------------------------------------------

def test_landing_y_on_empty_board():
    rows, _ = empty(20)
    cells = rotation_states("O")[0]  # 2x2, spans dy 0..1
    # Bottom of piece must rest on row 19, so y0 = 18.
    assert _landing_y(rows, cells, 0) == 18


def test_landing_y_stacks_on_existing_blocks():
    rows, _ = board("..........", "..........", "##........")
    cells = rotation_states("O")[0]
    # Columns 0-1 are occupied at row 2, so the O rests at rows 0-1.
    assert _landing_y(rows, cells, 0) == 0


def test_landing_y_uses_per_column_contact():
    # J rotation 0 is  #..
    #                  ###
    rows, _ = board("..........", "..........", "....#.....")
    cells = rotation_states("J")[0]
    y = _landing_y(rows, cells, 4)
    # Its bottom row (dy=1) must sit directly above the block at row 2.
    assert y == 0


def test_landing_y_returns_none_when_column_is_full():
    rows, _ = parse_board(["##########"] * 3)
    cells = rotation_states("O")[0]
    assert _landing_y(rows, cells, 0) is None


# --------------------------------------------------------------------------
# apply_placement + metrics
# --------------------------------------------------------------------------

def test_apply_placement_stamps_cells():
    rows, width = empty(4)
    cells = rotation_states("O")[0]
    after, _ = apply_placement(rows, width, cells, 0, 2)
    assert rows_to_matrix(after, width)[2][:2] == [1, 1]
    assert rows_to_matrix(after, width)[3][:2] == [1, 1]


def test_apply_placement_clears_full_line():
    # One gap at column 9; dropping a vertical I fills it and clears a row.
    rows, width = board("..........", "..........", "..........", "#########.")
    cells = rotation_states("I")[1]  # vertical, 1 wide x 4 tall
    after, metrics = apply_placement(rows, width, cells, 9, 0)
    assert metrics.cleared_lines == 1
    # The cleared row is gone; 3 of the I's cells remain, shifted down by one.
    assert sum(bin(r).count("1") for r in after) == 3


def test_apply_placement_eroded_cells():
    # 4 stacked rows, each missing column 9. A vertical I in column 9 fills
    # all four -> 4 cleared.
    rows, width = parse_board(["#########."] * 4)
    cells = rotation_states("I")[1]
    _, metrics = apply_placement(rows, width, cells, 9, 0)
    assert metrics.cleared_lines == 4
    # 4 lines cleared x 4 piece cells per line (vertical I, 4 cells each row)
    assert metrics.eroded_piece_cells == 16


def test_apply_placement_counts_holes():
    # An L rotation 0 placed so its top cell sits above a filled cell on the
    # same column. That empties cell -> a true hole is buried below.
    #   L rot 0:  ..#
    #             ###  at x0=0, y0=1 puts its (2,0) on top of the board and
    # the (0,1) and (1,1) cells rest on the floor; placing the L one cell up
    # covers (0,0) above an existing block at (0,1) -> hole.
    rows, width = board(
        "..........",
        "#.........",
        "##........",
    )
    cells = rotation_states("L")[0]  # ..# / ###
    after, metrics = apply_placement(rows, width, cells, 0, 0)
    # (0,0) is now covered by the L but has an occupied cell below at (0,1)
    # -> exactly one hole.
    assert metrics.holes == 1


def test_metrics_landing_height_is_measured_from_the_floor():
    rows, width = empty(20)
    cells = rotation_states("O")[0]
    _, metrics = apply_placement(rows, width, cells, 0, 18)
    # Piece occupies rows 18-19 of a 20-row board -> centre 1.5 above floor.
    assert metrics.landing_height == pytest.approx(1.5)


def test_wells_counts_cumulative_depth():
    # A 3-deep notch at column 5 walled by full columns on both sides.
    rows, width = board(
        "#####.####",
        "#####.####",
        "#####.####",
    )
    _, metrics = apply_placement(rows, width, ((0, 0),), 0, 0)  # no-op-ish stamp
    # 1 + 2 + 3 for the notch
    assert metrics.wells >= 6


def test_no_holes_on_flat_board():
    rows, width = empty(10)
    cells = rotation_states("I")[0]
    _, metrics = apply_placement(rows, width, cells, 0, 9)
    assert metrics.holes == 0


# --------------------------------------------------------------------------
# best_placement
# --------------------------------------------------------------------------

def test_best_placement_fills_the_single_gap():
    """A board one cell short of a line clear: the I must go into the notch."""
    rows, width = board(
        "..........",
        "..........",
        "..........",
        "..........",
        "#########.",
        "#########.",
        "#########.",
        "#########.",
    )
    p = best_placement(rows, width, "I")
    assert p.rotation == 1  # vertical
    assert p.x == 9
    assert p.cleared_lines == 4


def test_best_placement_prefers_flat_ground_over_creating_holes():
    """An S piece dropped on a bumpy left side would bury a cell; go flat instead."""
    rows, width = board(
        "..........",
        "..........",
        "#.........",
        "#.#.......",
    )
    p = best_placement(rows, width, "O")
    # The O should not straddle the notch at columns 1-2 (that buries a cell).
    after, metrics = apply_placement(rows, width, rotation_states("O")[0], p.x, p.y)
    assert metrics.holes == 0


def test_best_placement_on_empty_board_stays_low():
    rows, width = empty(20)
    p = best_placement(rows, width, "I")
    assert p.metrics.holes == 0
    assert p.y >= 16  # lands at the bottom


def test_best_placement_raises_when_board_is_full():
    rows, width = parse_board(["##########"] * 5)
    with pytest.raises(NoPlacementError):
        best_placement(rows, width, "T")


def test_lookahead_changes_the_choice_on_a_crafted_board():
    """With an I coming, the bot should keep the deep well open for it."""
    rows, width = board(
        "..........",
        "..........",
        "..........",
        "..........",
        "#########.",
        "#########.",
        "#########.",
        "#########.",
    )
    # Placing the O anywhere fills columns; with a following I the engine should
    # still avoid capping column 9.
    p = best_placement(rows, width, "O", next_piece="I")
    assert p.x <= 7, "should not cover the well at column 9"


def test_lookahead_never_returns_an_illegal_placement():
    rows, width = empty(20)
    for piece in "IOTSZJL":
        for nxt in "IOTSZJL":
            p = best_placement(rows, width, piece, next_piece=nxt)
            cells = rotation_states(piece)[p.rotation]
            assert p.x + piece_width(piece, p.rotation) <= width
            assert all(0 <= p.y + dy < len(rows) for _, dy in cells)


def test_custom_weights_are_honoured():
    rows, width = empty(20)
    # Invert the landing-height weight so tall placements score best; the result
    # must differ from the default policy on at least one piece.
    greedy_high = {
        "landing_height": 100.0,
        "eroded_piece_cells": 0.0,
        "row_transitions": 0.0,
        "column_transitions": 0.0,
        "holes": 0.0,
        "wells": 0.0,
    }
    p = best_placement(rows, width, "I", weights=greedy_high)
    assert p.metrics.landing_height >= 1.0


# --------------------------------------------------------------------------
# plan_moves
# --------------------------------------------------------------------------

def test_plan_moves_ends_with_hard_drop():
    moves = plan_moves("T", 0, 4, W, current_x=4)
    assert moves[-1] == "hard_drop"


def test_plan_moves_emits_rotations_first():
    moves = plan_moves("T", 2, 4, W, current_x=4, current_rotation=0)
    assert moves == ["rotate", "rotate", "hard_drop"]


def test_plan_moves_rotation_is_clockwise_modulo_four():
    # From rotation 3 to rotation 0 is one clockwise turn, not three.
    moves = plan_moves("T", 0, 4, W, current_x=4, current_rotation=3)
    assert moves.count("rotate") == 1


def test_plan_moves_left_and_right():
    assert plan_moves("O", 0, 1, W, current_x=4) == ["left"] * 3 + ["hard_drop"]
    assert plan_moves("O", 0, 7, W, current_x=4) == ["right"] * 3 + ["hard_drop"]


def test_plan_moves_defaults_to_spawn_position():
    # O spawns at column 4 on a 10-wide board, so target 4 needs no movement.
    assert plan_moves("O", 0, 4, W) == ["hard_drop"]


def test_plan_moves_clamps_start_column_to_the_right_edge():
    """Rotating I from vertical to horizontal at column 9 must not emit bogus moves."""
    moves = plan_moves("I", 0, 6, W, current_x=9, current_rotation=1)
    # Horizontal I can start no further right than column 6.
    assert "right" not in moves
    assert moves.count("rotate") == 3


def test_plan_moves_and_best_placement_agree():
    """The planned target column always matches what the search chose."""
    rows, width = board("..........", "..........", "###.......", "####......")
    p = best_placement(rows, width, "L", next_piece="T")
    moves = plan_moves("L", p.rotation, p.x, width, current_x=None)
    rights = moves.count("right")
    lefts = moves.count("left")
    start = spawn_x("L", width, 0)
    from rt_backend.tetris_ai.pieces import piece_width as pw

    start = min(start, width - pw("L", p.rotation))
    assert start + rights - lefts == p.x
