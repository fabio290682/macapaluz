import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "macapaluz_robusto.db"
DB_ENV = os.getenv("MACAPALUZ_DB_PATH")
if DB_ENV:
    DB_PATH = Path(DB_ENV)
else:
    DB_PATH = DEFAULT_DB_PATH if DEFAULT_DB_PATH.exists() else (ROOT / "macapaluz.db")

ROBUST_SCHEMA = ROOT / "database" / "sqlite_schema_robust.sql"
LEGACY_SCHEMA = ROOT / "database" / "sqlite_schema.sql"
SEED_SQL = ROOT / "database" / "seed_sqlite.sql"
QUALITY_VIEWS = ROOT / "database" / "quality_views.sql"


def run_sql(conn, path):
    conn.executescript(path.read_text(encoding="utf-8"))


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    if ROBUST_SCHEMA.exists():
        run_sql(conn, ROBUST_SCHEMA)
    elif LEGACY_SCHEMA.exists():
        run_sql(conn, LEGACY_SCHEMA)

    if QUALITY_VIEWS.exists():
        run_sql(conn, QUALITY_VIEWS)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pontos_ilp")
    points = cur.fetchone()[0]
    if users == 0 and points == 0 and SEED_SQL.exists():
        run_sql(conn, SEED_SQL)

    conn.commit()
    conn.close()
    return DB_PATH


if __name__ == "__main__":
    out = ensure_db()
    print(f"Banco pronto em: {out}")
