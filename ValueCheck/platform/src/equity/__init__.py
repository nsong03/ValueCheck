"""Equity research platform — hexagonal backend.

Layer boundaries (enforced by import-linter, see `.importlinter`):

    api -> application -> adapters -> ports -> domain

`domain` is pure (zero I/O); outer layers may import inward only.
"""

__version__ = "0.1.0"
