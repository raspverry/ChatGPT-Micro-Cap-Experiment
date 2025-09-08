# scripts/browser/actions/registry.py
from typing import Dict, Any, Callable

class ActionRegistry:
    """Registry for all browser actions"""
    _actions: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, aliases: list = None):
        """Decorator to register actions"""
        def decorator(func):
            cls._actions[name] = func
            if aliases:
                for alias in aliases:
                    cls._actions[alias] = func
            return func
        return decorator

    @classmethod
    async def execute(cls, name: str, tab, kwargs) -> Dict[str, Any]:
        """Execute a registered action"""
        if name not in cls._actions:
            raise ValueError(f"Unknown action: {name}")
        return await cls._actions[name](tab, kwargs)

    @classmethod
    def list_actions(cls) -> list:
        """List all registered actions"""
        return list(cls._actions.keys())