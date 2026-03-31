"""Tool system module - registry, decorators, and built-in tools.

Provides :func:`auto_discover_and_register` which scans every module
in ``agent_core.tools`` and calls any ``register_*_tools(registry)``
function it finds.  This eliminates the need to manually import each
tool module in a central location — new tool files are picked up
automatically.
"""

import importlib
import pkgutil

from agent_core.tools.registry import ToolRegistry

# Modules that should NOT be scanned for register_*_tools functions.
_SKIP_MODULES = frozenset({"registry"})


def auto_discover_and_register(registry: ToolRegistry) -> None:
    """Scan all modules under ``agent_core.tools`` and register their tools.

    Any public function whose name matches ``register_*_tools`` and
    accepts a single :class:`ToolRegistry` argument will be called.

    Args:
        registry: The registry to populate.
    """
    package = importlib.import_module("agent_core.tools")
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        if modname in _SKIP_MODULES or modname.startswith("_"):
            continue
        module = importlib.import_module(f"agent_core.tools.{modname}")
        for attr_name in dir(module):
            if attr_name.startswith("register_") and attr_name.endswith("_tools"):
                func = getattr(module, attr_name)
                if callable(func):
                    func(registry)
