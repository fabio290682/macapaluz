import os
import sqlite3
import hashlib
from pathlib import Path
import secrets


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
DEFAULT_PASSWORDS = {
    "admin@macapaluz.local": "Admin@123",
    "gestor@macapaluz.local": "Gestor@123",
    "tecnico1@macapaluz.local": "Tecnico@123",
    "operador@macapaluz.local": "Operador@123",
}
APP_ENV = os.getenv("MACAPALUZ_ENV", "development").strip().lower() or "development"


def is_production():
    return APP_ENV in {"prod", "production"}


def run_sql(conn, path):
    conn.executescript(path.read_text(encoding="utf-8"))


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def ensure_default_password_hashes(conn):
    if is_production():
        return
    rows = conn.execute("SELECT id, email, senha_hash FROM usuarios").fetchall()
    for row in rows:
        email = row[1]
        senha_hash = row[2] or ""
        if senha_hash.startswith("pbkdf2_sha256$"):
            continue
        default_password = DEFAULT_PASSWORDS.get(email)
        if not default_password:
            continue
        conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_password(default_password), row[0]))


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
    ensure_default_password_hashes(conn)

    conn.commit()
    conn.close()
    return DB_PATH


if __name__ == "__main__":
    out = ensure_db()
    print(f"Banco pronto em: {out}")
