"""Plugin discovery and lifecycle."""

from .engine import PluginEngine, PluginError, PluginSpec, get_plugin_engine

__all__ = ["PluginEngine", "PluginError", "PluginSpec", "get_plugin_engine"]
