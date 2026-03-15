"""Database schema."""
import sqlite3, os
SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_states (id INTEGER PRIMARY KEY, agent_id TEXT UNIQUE, state_data TEXT);
CREATE TABLE IF NOT EXISTS context_entries (id INTEGER PRIMARY KEY, entry_id TEXT UNIQUE, content TEXT);
"""
def init_database(db_path=None):
    if db_path is None:
        db_path = os.path.expanduser("~/.openplex/memory.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return db_path
