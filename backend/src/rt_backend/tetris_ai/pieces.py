"""Tetromino geometry.

Each rotation state is a tuple of ``(dx, dy)`` cell offsets, normalized so that
``min(dx) == 0`` and ``min(dy) == 0``. ``dx`` grows to the right, ``dy`` grows
downwards (row 0 is the top of the board), matching the board matrix the client
uploads.

All seven pieces expose exactly four rotation states so a client can always send
``rotation in 0..3``. For I/S/Z states 2/3 duplicate 0/1, and for O all four are
identical; the search deduplicates them so it never evaluates the same shape
twice and always reports the smallest equivalent rotation index.
"""
from __future__ import annotations

from typing import Dict, Tuple

Cells = Tuple[Tuple[int, int], ...]
Rotations = Tuple[Cells, Cells, Cells, Cells]

_I_H: Cells = ((0, 0), (1, 0), (2, 0), (3, 0))
_I_V: Cells = ((0, 0), (0, 1), (0, 2), (0, 3))
_O: Cells = ((0, 0), (1, 0), (0, 1), (1, 1))
_S_H: Cells = ((1, 0), (2, 0), (0, 1), (1, 1))
_S_V: Cells = ((0, 0), (0, 1), (1, 1), (1, 2))
_Z_H: Cells = ((0, 0), (1, 0), (1, 1), (2, 1))
_Z_V: Cells = ((1, 0), (0, 1), (1, 1), (0, 2))

PIECES: Dict[str, Rotations] = {
    # ####
    "I": (_I_H, _I_V, _I_H, _I_V),
    # ##
    # ##
    "O": (_O, _O, _O, _O),
    # .#.  #.   ###  .#
    # ###  ##   .#.  ##
    #       #        .#
    "T": (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (0, 1), (1, 1), (0, 2)),
        ((0, 0), (1, 0), (2, 0), (1, 1)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    # .##  #.
    # ##.  ##
    #       .#
    "S": (_S_H, _S_V, _S_H, _S_V),
    # ##.  .#
    # .##  ##
    #      #.
    "Z": (_Z_H, _Z_V, _Z_H, _Z_V),
    # #..  ##   ###  .#
    # ###  #.   ..#  .#
    #      #.        ##
    "J": (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (1, 0), (0, 1), (0, 2)),
        ((0, 0), (1, 0), (2, 0), (2, 1)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    # ..#  #.   ###  ##
    # ###  #.   #..  .#
    #      ##        .#
    "L": (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((0, 0), (0, 1), (0, 2), (1, 2)),
        ((0, 0), (1, 0), (2, 0), (0, 1)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
}

PIECE_NAMES: Tuple[str, ...] = ("I", "O", "T", "S", "Z", "J", "L")


def normalize_piece(name: str) -> str:
    """Accept ``i``/``I``/``"1"``-free variants and return the canonical letter."""
    key = name.strip().upper()
    if key not in PIECES:
        raise ValueError(f"未知方块类型：{name!r}，合法值：{', '.join(PIECE_NAMES)}")
    return key


def rotation_states(name: str) -> Rotations:
    return PIECES[normalize_piece(name)]


def distinct_rotations(name: str) -> Tuple[int, ...]:
    """Rotation indices that produce geometrically distinct shapes.

    Returns the *smallest* index for each distinct shape, e.g. ``(0, 1)`` for I
    and ``(0,)`` for O.
    """
    states = PIECES[normalize_piece(name)]
    seen: dict[Cells, int] = {}
    for idx, cells in enumerate(states):
        key = tuple(sorted(cells))
        if key not in seen:
            seen[key] = idx
    return tuple(sorted(seen.values()))


def piece_width(name: str, rotation: int) -> int:
    cells = PIECES[normalize_piece(name)][rotation % 4]
    return max(dx for dx, _ in cells) + 1


def spawn_x(name: str, board_width: int, rotation: int = 0) -> int:
    """Default leftmost column of a freshly spawned piece (centered, floored)."""
    return max(0, (board_width - piece_width(name, rotation)) // 2)
