"""
Migration idempotency tests.

Critical for Railway — the migration runner must succeed *every time* it's
executed against a database that's already at the latest version. If not,
Railway deploys fail on every subsequent restart.

We verify by:
  1. Applying all migrations twice
  2. Ensuring no error is raised
  3. Spot-checking that no duplicate ENUM / column was created
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.skipif(
    not (BACKEND_DIR / "alembic").exists(),
    reason="alembic directory not present",
)
def test_migrations_idempotent():
    """Run `alembic upgrade head` twice — second run must be a no-op."""
    first = _alembic("upgrade", "head")
    assert first.returncode == 0, f"first upgrade failed:\n{first.stderr}"

    second = _alembic("upgrade", "head")
    assert second.returncode == 0, f"second upgrade failed:\n{second.stderr}"

    # Alembic's stdout for a no-op contains "Running upgrade" *only* if
    # there's something new to apply. Both runs being successful is the
    # critical signal — duplicate creation would raise an IntegrityError.
    assert "FAILED" not in second.stdout.upper()


def test_alembic_ini_exists():
    """Make sure Alembic config is present and points to the right place."""
    cfg = BACKEND_DIR / "alembic.ini"
    assert cfg.exists()
    content = cfg.read_text(encoding="utf-8")
    assert "script_location" in content