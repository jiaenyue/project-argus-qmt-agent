"""Argus MCP Server - Model Context Protocol implementation for Project Argus.

This module provides a standard MCP server implementation that integrates
with the existing data_agent_service to provide AI assistants with access
to quantitative trading data and analysis capabilities.
"""

__version__ = "1.0.0"
__author__ = "Project Argus Team"

from .server import ArgusMCPServer
from .models import *
from .tools import *

__all__ = [
    "ArgusMCPServer",
    "models",
    "tools",
]