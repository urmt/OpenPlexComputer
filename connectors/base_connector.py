"""OpenPlexComputer - Base Connector Interface

Defines the abstract base class for all connectors and the
connector registry for managing 400+ potential integrations.
"""

import os
import sys
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from sandbox import get_vault, SecureVault, AuditLogger
from governance import ApprovalWorkflow, ActionType

logger = logging.getLogger("openplex.connectors.base")


class ConnectorStatus(Enum):
    """Status of a connector."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ConnectorConfig:
    """Configuration for a connector."""
    name: str
    api_base_url: str
    timeout_seconds: int = 30
    retry_attempts: int = 3
    require_approval: bool = True
    rate_limit_per_minute: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    """Abstract base class for all connectors."""
    
    def __init__(self, config: ConnectorConfig, vault: Optional[SecureVault] = None):
        self.config = config
        self.vault = vault or get_vault()
        self._audit = AuditLogger()
        self._approval = ApprovalWorkflow()
        self._status = ConnectorStatus.DISCONNECTED
        self._lock = threading.Lock()
        self._request_count = 0
        self._last_request_time = datetime.utcnow()
        self._credentials: Optional[Dict] = None
        
    @property
    def status(self) -> ConnectorStatus:
        return self._status
        
    @property
    def is_connected(self) -> bool:
        return self._status == ConnectorStatus.CONNECTED
        
    @abstractmethod
    def authenticate(self) -> bool:
        pass
        
    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        pass
        
    def disconnect(self) -> bool:
        with self._lock:
            self._status = ConnectorStatus.DISCONNECTED
            self._credentials = None
        self._audit.log_event(
            event_type="CONNECTOR",
            actor="system",
            resource=f"connector:{self.config.name}",
            action="disconnect",
            status="success"
        )
        return True
        
    def _check_rate_limit(self) -> bool:
        now = datetime.utcnow()
        time_diff = (now - self._last_request_time).total_seconds()
        if time_diff >= 60:
            self._request_count = 0
            self._last_request_time = now
        if self._request_count >= self.config.rate_limit_per_minute:
            return False
        self._request_count += 1
        return True
        
    def _get_credentials_from_vault(self, credential_key: str) -> Optional[str]:
        return self.vault.retrieve(credential_key, requester=self.config.name)


class ConnectorRegistry:
    """Registry for managing 400+ potential connector integrations."""
    
    _instance: Optional['ConnectorRegistry'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
        self._connectors: Dict[str, BaseConnector] = {}
        self._connector_classes: Dict[str, Type[BaseConnector]] = {}
        self._audit = AuditLogger()
        self._initialized = True
        
    def register_connector_class(self, name: str, 
                                  connector_class: Type[BaseConnector]) -> bool:
        self._connector_classes[name] = connector_class
        logger.info(f"Registered connector class: {name}")
        return True
        
    def create_connector(self, name: str, config: ConnectorConfig) -> Optional[BaseConnector]:
        if name not in self._connector_classes:
            logger.error(f"Connector class not registered: {name}")
            return None
        connector = self._connector_classes[name](config)
        self._connectors[name] = connector
        self._audit.log_event(
            event_type="CONNECTOR",
            actor="system",
            resource=f"connector:{name}",
            action="create",
            status="success"
        )
        return connector
        
    def get_connector(self, name: str) -> Optional[BaseConnector]:
        return self._connectors.get(name)
        
    def list_connectors(self) -> List[str]:
        return list(self._connectors.keys())
        
    def health_check_all(self) -> Dict[str, Dict]:
        results = {}
        for name, connector in self._connectors.items():
            try:
                results[name] = connector.health_check()
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        return results
        
    def disconnect_all(self) -> bool:
        for name, connector in self._connectors.items():
            try:
                connector.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {name}: {e}")
        self._connectors.clear()
        return True


if __name__ == "__main__":
    print("OpenPlexComputer Base Connector")
    print("=" * 50)
    print("\nConnector Registry Test:")
    registry = ConnectorRegistry()
    print(f"  Registry initialized: {registry._initialized}")
    print(f"  Registered classes: {len(registry._connector_classes)}")
    print("\n✓ Base Connector test complete")
