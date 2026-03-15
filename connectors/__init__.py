"""OpenPlexComputer - Connectivity Layer: Multi-Tool Coordination

Interface with 400+ potential connectors for external tool integration.
Provides unified API for GitHub, Slack, and other services with
mandatory approval workflows and comprehensive audit trails.
"""

from .github_connector import GitHubConnector
from .slack_connector import SlackConnector
from .base_connector import BaseConnector, ConnectorRegistry

__all__ = [
    'GitHubConnector',
    'SlackConnector', 
    'BaseConnector',
    'ConnectorRegistry'
]
