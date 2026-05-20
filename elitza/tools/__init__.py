"""Central registry for all Elitza tools.

Each tool file calls registry.register() at module level to declare its
schema, handler, and metadata. The agent queries the registry to get
tool definitions and dispatch calls.

Design: Inspired by Hermes Agent's tools/registry.py but simplified.
"""

import ast
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolEntry:
    """Metadata for a single registered tool."""

    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "is_async", "description",
    )

    def __init__(self, name, toolset, schema, handler, check_fn=None,
                 is_async=False, description=""):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.is_async = is_async
        self.description = description


class ToolRegistry:
    """Central tool registry. Singleton pattern."""

    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        toolset: str,
        schema: Dict[str, Any],
        handler: Callable,
        check_fn: Optional[Callable] = None,
        is_async: bool = False,
        description: str = "",
    ):
        """Register a tool.

        Args:
            name: Tool name (used by the LLM in tool_calls)
            toolset: Tool group (terminal, file, web, etc.)
            schema: OpenAI function calling JSON schema
            handler: Callable that executes the tool
            check_fn: Optional availability check
            is_async: Whether the handler is async
            description: Human-readable description
        """
        if name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", name)
        self._tools[name] = ToolEntry(
            name=name, toolset=toolset, schema=schema,
            handler=handler, check_fn=check_fn, is_async=is_async,
            description=description,
        )
        logger.debug("Registered tool: %s (toolset=%s)", name, toolset)

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        return dict(self._tools)

    def get_tools_for_toolsets(
        self,
        enabled: Optional[List[str]] = None,
        disabled: Optional[List[str]] = None,
    ) -> List[ToolEntry]:
        """Return tools filtered by toolset."""
        tools = list(self._tools.values())
        if enabled:
            enabled_set = set(enabled)
            tools = [t for t in tools if t.toolset in enabled_set]
        if disabled:
            disabled_set = set(disabled)
            tools = [t for t in tools if t.toolset not in disabled_set]
        return tools

    def get_openai_schemas(
        self,
        enabled_toolsets: Optional[List[str]] = None,
        disabled_toolsets: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return OpenAI-format tool schemas for the enabled toolsets."""
        tools = self.get_tools_for_toolsets(enabled_toolsets, disabled_toolsets)
        return [
            {"type": "function", "function": t.schema}
            for t in tools
        ]

    def dispatch(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool by name with given arguments."""
        entry = self._tools.get(name)
        if entry is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = entry.handler(**args)
            if isinstance(result, str):
                return result
            return json.dumps(result, default=str)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return json.dumps({"error": str(e)})


# Global singleton
registry = ToolRegistry()


def _is_registry_register_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "register"
        and isinstance(func.value, ast.Name)
        and func.value.id == "registry"
    )


def _module_registers_tools(module_path: Path) -> bool:
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (OSError, SyntaxError):
        return False
    return any(_is_registry_register_call(stmt) for stmt in tree.body)


def discover_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """Import built-in self-registering tool modules."""
    tools_path = tools_dir or Path(__file__).resolve().parent
    module_names = [
        f"elitza.tools.{path.stem}"
        for path in sorted(tools_path.glob("*.py"))
        if path.name not in {"__init__.py", "registry.py"}
        and _module_registers_tools(path)
    ]
    imported: List[str] = []
    for mod_name in module_names:
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)
    return imported
