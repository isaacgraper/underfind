import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cache.sqlite3"

class SQLiteClient:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                timestamp TEXT
            )
        """)
        self.conn.commit()

    def save_search_history(self, query):
        self.conn.execute(
            "INSERT OR REPLACE INTO search_history VALUES (?, ?, ?)",
            (query, timestamp)
        )
        self.conn.commit()
