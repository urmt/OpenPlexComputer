"""Memory store."""
import sqlite3, json
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class AgentState:
    agent_id: str
    session_id: str
    state_data: Dict[str, Any]
    status: str = "active"

@dataclass
class ContextEntry:
    entry_id: str
    agent_id: str
    session_id: str
    entry_type: str
    content: str

class MemoryStore:
    def __init__(self, db_path=None):
        from .schema import init_database
        self.db_path = db_path or init_database()
    
    def save_agent_state(self, state: AgentState) -> bool:
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT OR REPLACE INTO agent_states (agent_id, state_data) VALUES (?, ?)",
                    (state.agent_id, json.dumps(state.state_data)))
        conn.commit()
        conn.close()
        return True
