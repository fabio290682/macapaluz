import sqlite3
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "macapaluz_robusto.db"
DB_PATH = Path(os.getenv("MACAPALUZ_DB_PATH", str(DEFAULT_DB_PATH)))
if not DB_PATH.exists():
    DB_PATH = ROOT / "macapaluz.db"
SQL_PATH = ROOT / "database" / "quality_views.sql"


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco nao encontrado: {DB_PATH}")
    sql = SQL_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(sql)
    conn.commit()
    conn.close()
    print(f"Views aplicadas em {DB_PATH}")


if __name__ == "__main__":
    main()
