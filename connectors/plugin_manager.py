"""Plugin Manager for connectors."""
import os, json
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class PluginStatus(Enum):
    AVAILABLE = "available"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"

@dataclass
class ConnectorPlugin:
    plugin_id: str
    name: str
    description: str
    version: str
    author: str
    connector_class: str
    dependencies: List[str]
    config_schema: Dict
    status: PluginStatus = PluginStatus.AVAILABLE

class PluginManager:
    BUILTIN_PLUGINS = [
        {"plugin_id": "connector-github", "name": "GitHub Connector", "description": "GitHub integration", "version": "1.0.0", "author": "OpenPlex", "connector_class": "connectors.github_connector.GitHubConnector", "dependencies": ["requests"], "config_schema": {"token": {"type": "string", "required": True, "secret": True}}},
        {"plugin_id": "connector-slack", "name": "Slack Connector", "description": "Slack integration", "version": "1.0.0", "author": "OpenPlex", "connector_class": "connectors.slack_connector.SlackConnector", "dependencies": ["slack-sdk"], "config_schema": {"bot_token": {"type": "string", "required": True, "secret": True}}},
    ]
    
    def __init__(self, plugin_dirs=None):
        self.plugin_dirs = plugin_dirs or [os.path.expanduser("~/.openplex/plugins")]
        self._plugins: Dict[str, ConnectorPlugin] = {}
        self._register_builtin_plugins()
    
    def _register_builtin_plugins(self):
        for plugin_def in self.BUILTIN_PLUGINS:
            plugin = ConnectorPlugin(**plugin_def)
            self._plugins[plugin.plugin_id] = plugin
    
    def load_plugin(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.LOADED
        return True
    
    def activate_plugin(self, plugin_id: str, config=None) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.ACTIVE
        return True
    
    def get_plugin(self, plugin_id: str):
        return self._plugins.get(plugin_id)
    
    def list_plugins(self, status=None):
        plugins = list(self._plugins.values())
        if status:
            plugins = [p for p in plugins if p.status == status]
        return plugins
    
    def get_stats(self):
        by_status = {}
        for p in self._plugins.values():
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
        return {"total_plugins": len(self._plugins), "by_status": by_status}
