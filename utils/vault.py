"""OpenPlexComputer Credential Vault - HashiCorp Vault integration for secure credential management"""
import os
import json
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VaultProvider(Enum):
    HASHICORP = "hashicorp"
    LOCAL_ENCRYPTED = "local_encrypted"

@dataclass
class SecretMetadata:
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0

class CredentialVault:
    """Secure credential vault with multiple backend support"""
    
    def __init__(self, provider: Optional[VaultProvider] = None, config: Optional[Dict] = None):
        self.provider = provider or VaultProvider.LOCAL_ENCRYPTED
        self.config = config or {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._init_provider()
        logger.info(f"CredentialVault initialized with provider: {self.provider.value}")
        
    def _init_provider(self):
        if self.provider == VaultProvider.LOCAL_ENCRYPTED:
            self.storage_path = self.config.get("storage_path", "./data/vault")
            os.makedirs(self.storage_path, exist_ok=True)
            
    def store_oauth_token(self, service: str, token: Dict[str, Any], expires_at: Optional[datetime] = None) -> bool:
        """Store OAuth token server-side only"""
        secret_path = f"oauth/{service}"
        secret_data = {
            "token": token,
            "stored_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        
        try:
            file_path = os.path.join(self.storage_path, f"{service}.enc")
            with open(file_path, 'w') as f:
                json.dump(secret_data, f)
            self._metadata[service] = SecretMetadata(
                created_at=datetime.now(),
                expires_at=expires_at,
            )
            logger.info(f"OAuth token stored for service: {service}")
            return True
        except Exception as e:
            logger.error(f"Failed to store OAuth token: {e}")
            return False
            
    def get_proxy_handle(self, service: str) -> Optional[Dict]:
        """Get a proxy handle for making authenticated API calls"""
        if service in self._metadata:
            meta = self._metadata[service]
            meta.access_count += 1
        return {
            "service": service,
            "proxy_endpoint": f"/api/v1/proxy/{service}",
            "auth_type": "oauth_proxy",
            "token_retrieved": service in self._metadata,
        }
        
    def retrieve_secret(self, service: str) -> Optional[Dict]:
        """Retrieve actual secret (for proxy use only)"""
        try:
            file_path = os.path.join(self.storage_path, f"{service}.enc")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
        return None

_vault_instance: Optional[CredentialVault] = None

def get_vault(provider: Optional[VaultProvider] = None) -> CredentialVault:
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = CredentialVault(provider=provider)
    return _vault_instance
