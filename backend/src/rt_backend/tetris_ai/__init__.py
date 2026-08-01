"""Tetris AI decision service.

Stateless: the client owns the game loop and uploads the current board plus the
piece it needs to place; this module answers *where* to put it and *how* to get
there.
"""
