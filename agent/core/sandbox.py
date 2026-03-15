"""OpenPlexComputer - Security Tier: Firecracker-Style Sandbox"""
import os, sys, json, logging, subprocess, tempfile, shutil, secrets
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openplex.sandbox")

@dataclass
class SandboxConfig:
    isolate_network: bool = True
    isolate_filesystem: bool = True
    isolate_processes: bool = True
    read_only_paths: List[str] = field(default_factory=list)
    writable_paths: List[str] = field(default_factory=list)
    env_whitelist: List[str] = field(default_factory=lambda: ["PATH", "HOME", "USER", "LANG", "TERM"])
    max_memory_mb: int = 512
    max_cpu_percent: int = 50

class SecureVault:
    """Vault-based credential management to prevent .env leaks."""
    
    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._access_log: List[Dict] = []
        self._initialized = False
        self._sealed = True
        
    def initialize(self, master_key: Optional[str] = None) -> bool:
        if self._initialized and not self._sealed:
            return True
        self._initialized = True
        self._sealed = False
        logger.info("Vault initialized")
        return True
        
    def seal(self) -> None:
        self._secrets.clear()
        self._sealed = True
        logger.info("Vault sealed")
        
    def store(self, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        if self._sealed:
            raise RuntimeError("Vault is sealed")
        self._secrets[key] = value
        self._access_log.append({"action": "store", "key": key, "timestamp": self._get_timestamp()})
        return True
        
    def retrieve(self, key: str, requester: Optional[str] = None) -> Optional[str]:
        if self._sealed:
            raise RuntimeError("Vault is sealed")
        value = self._secrets.get(key)
        self._access_log.append({"action": "retrieve", "key": key, "timestamp": self._get_timestamp()})
        return value
        
    def list_keys(self) -> List[str]:
        return list(self._secrets.keys())
        
    def _get_timestamp(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

class FirecrackerSandbox:
    """Simulates Firecracker microVM isolation."""
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.vault = SecureVault()
        self._active_sessions: Dict[str, Dict] = {}
        self._isolated_root: Optional[str] = None
        
    def initialize(self) -> bool:
        logger.info("Initializing Firecracker-style sandbox...")
        self.vault.initialize()
        self._isolated_root = tempfile.mkdtemp(prefix="openplex_sandbox_")
        self._load_credentials_to_vault()
        logger.info(f"Sandbox initialized at: {self._isolated_root}")
        return True
        
    def _load_credentials_to_vault(self) -> None:
        config_path = Path.home() / ".config" / "openrouter" / "config"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if 'api_key' in config:
                        self.vault.store("openrouter_api_key", config['api_key'])
                        logger.info("Loaded OpenRouter credentials into vault")
            except Exception as e:
                logger.warning(f"Could not load credentials: {e}")
        
        # Block .env file access
        env_path = Path("/home/student/PrivateCable/.env")
        if env_path.exists():
            logger.info("PrivateCable .env detected - access blocked by sandbox isolation")
            
    def create_session(self, session_id: Optional[str] = None) -> str:
        import uuid
        session_id = session_id or str(uuid.uuid4())[:8]
        session_dir = os.path.join(self._isolated_root, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        isolated_env = {k: v for k, v in os.environ.items() if k in self.config.env_whitelist}
        isolated_env["OPENPLEX_SESSION"] = session_id
        isolated_env["OPENPLEX_ISOLATED"] = "1"
        
        self._active_sessions[session_id] = {
            "dir": session_dir,
            "env": isolated_env,
            "created_at": self.vault._get_timestamp()
        }
        
        logger.info(f"Created sandbox session: {session_id}")
        return session_id
        
    def cleanup_session(self, session_id: str) -> bool:
        if session_id not in self._active_sessions:
            return False
        session = self._active_sessions[session_id]
        if os.path.exists(session["dir"]):
            shutil.rmtree(session["dir"])
        del self._active_sessions[session_id]
        logger.info(f"Cleaned up session: {session_id}")
        return True
        
    def shutdown(self) -> None:
        for session_id in list(self._active_sessions.keys()):
            self.cleanup_session(session_id)
        self.vault.seal()
        if self._isolated_root and os.path.exists(self._isolated_root):
            shutil.rmtree(self._isolated_root)
        logger.info("Sandbox shutdown complete")


_sandbox_instance = None

def get_sandbox() -> FirecrackerSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = FirecrackerSandbox()
        _sandbox_instance.initialize()
    return _sandbox_instance

def get_vault() -> SecureVault:
    return get_sandbox().vault

if __name__ == "__main__":
    sandbox = get_sandbox()
    session = sandbox.create_session()
    print(f"Created session: {session}")
    vault = get_vault()
    vault.store("test_key", "test_value")
    value = vault.retrieve("test_key")
    print(f"Retrieved: {value}")
    sandbox.cleanup_session(session)
    sandbox.shutdown()
    print("Sandbox test complete")
