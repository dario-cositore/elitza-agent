---
name: elitza-agent
description: Configure, extend, or contribute to Elitza Agent.
---

# Elitza Agent Skill

## Configuration

Config file: `~/.elitza/config.yaml`
Env file: `~/.elitza/.env` (for OPENROUTER_API_KEY)

## CLI Commands

- `elitza` -- Interactive REPL
- `elitza -m "message"` -- Single message
- `elitza --list-tools` -- List available tools
- `elitza --model anthropic/claude-sonnet-4` -- Use specific model
- `elitza --toolsets terminal,file` -- Enable specific toolsets
- `elitza -v` -- Verbose mode (shows tool calls)

## Project Structure

```
elitza-agent/
  elitza/
    agent.py          # Core agent loop
    cli.py            # Interactive CLI
    config.py         # Config loading
    constants.py      # Paths and URLs
    tools/
      __init__.py     # Tool registry + discovery
      terminal.py     # Shell execution
      file_ops.py     # read_file, write_file, patch, search
    skills/           # Built-in skills
```

## Adding a New Tool

1. Create a function in elitza/tools/
2. Call `registry.register()` at module level
3. The tool is auto-discovered on import

Example:

```python
from elitza.tools.registry import registry

def my_tool(query: str) -> str:
    return f"Result for: {query}"

registry.register(
    name="my_tool",
    toolset="custom",
    schema={
        "name": "my_tool",
        "description": "Does something useful",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    handler=my_tool,
    description="My custom tool",
)
```
