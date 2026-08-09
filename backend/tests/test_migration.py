import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrades_empty_database(tmp_path):
    database_path = tmp_path / "migration.db"
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database_path}",
        # Migration correctness is independent of production runtime policy.
        # Use the isolated test profile so SQLite remains an allowed target.
        "ENVIRONMENT": "testing",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    tables = set(inspect(create_engine(environment["DATABASE_URL"])).get_table_names())
    assert {
        "alembic_version",
        "users",
        "merchants",
        "media_assets",
        "service_applications",
        "application_events",
        "audit_logs",
        "operator_invites",
    }.issubset(tables)
