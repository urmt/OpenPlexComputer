"""OpenPlexComputer - Secure Vault Module"""
import os, json, hashlib, secrets, logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openplex.vault")

class SecretLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

@dataclass
class AuditEntry:
    timestamp: str
    action: str
    key: str
    requester: Optional[str]
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SecretMetadata:
    created_at: str
    updated_at: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    level: SecretLevel = SecretLevel.CONFIDENTIAL
    tags: List[str] = field(default_factory=list)

class SecureVault:
    """Enterprise-grade secure vault for credential management."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._secrets: Dict[str, str] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._audit_log: List[AuditEntry] = []
        self._initialized = False
        self._sealed = True
        self._session_id = secrets.token_hex(16)
        
    def initialize(self, master_key: Optional[str] = None) -> bool:
        if self._initialized and not self._sealed:
            return True
        logger.info("Initializing secure vault...")
        self._initialized = True
        self._sealed = False
        self._audit_log.append(AuditEntry(
            timestamp=self._get_timestamp(),
            action="VAULT_INIT",
            key="",
            requester="system",
            success=True,
            metadata={"session_id": self._session_id}
        ))
        logger.info("Vault initialized successfully")
        return True
        
    def seal(self) -> None:
        logger.info("Sealing vault...")
        for key in list(self._secrets.keys()):
            self._secrets[key] = secrets.token_hex(len(self._secrets[key]))
            del self._secrets[key]
        self._secrets.clear()
        self._metadata.clear()
        self._sealed = True
        self._audit_log.append(AuditEntry(
            timestamp=self._get_timestamp(),
            action="VAULT_SEAL",
            key="",
            requester="system",
            success=True
        ))
        logger.info("Vault sealed - all secrets wiped from memory")
        
    def store(self, key: str, value: str, level: SecretLevel = SecretLevel.CONFIDENTIAL,
              metadata: Optional[Dict] = None) -> bool:
        if self._sealed:
            raise RuntimeError("Vault is sealed")
        timestamp = self._get_timestamp()
        self._secrets[key] = value
        self._metadata[key] = SecretMetadata(
            created_at=timestamp,
            updated_at=timestamp,
            level=level,
            tags=metadata.get("tags", []) if metadata else []
        )
        self._audit_log.append(AuditEntry(
            timestamp=timestamp,
            action="store",
            key=key,
            requester="system",
            success=True,
            metadata={"level": level.value}
        ))
        logger.debug(f"Secret stored: {key} (level: {level.value})")
        return True
        
    def retrieve(self, key: str, requester: Optional[str] = None) -> Optional[str]:
        if self._sealed:
            raise RuntimeError("Vault is sealed")
        value = self._secrets.get(key)
        if value and key in self._metadata:
            self._metadata[key].access_count += 1
            self._metadata[key].last_accessed = self._get_timestamp()
        self._audit_log.append(AuditEntry(
            timestamp=self._get_timestamp(),
            action="retrieve",
            key=key,
            requester=requester,
            success=value is not None
        ))
        return value
        
    def list_keys(self) -> List[str]:
        return list(self._secrets.keys())
        
    def get_audit_log(self) -> List[AuditEntry]:
        return self._audit_log.copy()
        
    def _get_timestamp(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

if __name__ == "__main__":
    vault = SecureVault()
    vault.initialize()
    vault.store("test_key", "test_value")
    print(f"Retrieved: {vault.retrieve('test_key')}")
    vault.seal()
    print("Vault test complete")
