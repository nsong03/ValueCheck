"""Guard: the import-linter boundary contract runs and passes in the suite.

Mirrors `make contracts` so a hexagonal-boundary violation fails pytest too.
Shells out to the `lint-imports` console script (stable) rather than depending
on import-linter's internal API (which changes between releases).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# .importlinter lives at the platform root: tests/unit/ -> tests/ -> platform/
_PLATFORM_ROOT = Path(__file__).resolve().parents[2]


def test_import_linter_contracts_pass() -> None:
    result = subprocess.run(
        ["lint-imports"],
        cwd=_PLATFORM_ROOT,
        capture_output=True,
        # import-linter's output is UTF-8; don't rely on the locale codec
        # (e.g. cp949 on Korean Windows), which chokes on its banner art.
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, f"import-linter failed:\n{result.stdout}\n{result.stderr}"
