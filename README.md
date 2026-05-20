# Elitza Agent

OpenRouter-native AI agent CLI. One-liner install, full tool-calling, streaming responses.

## Install

```bash
curl -fsSL https://elitza.life/install.sh | bash
```

This will:
1. Install `uv` (Python package manager) if needed
2. Clone and install Elitza Agent
3. Add `elitza` to your PATH
4. Run the setup wizard

## Quick Start

```bash
# Configure your OpenRouter API key
elitza setup

# Start chatting
elitza

# Single message
elitza -m "What's the weather like?"

# Use a specific model
elitza --model anthropic/claude-opus-4 -m "Hello"

# List available tools
elitza --list-tools
```

## Requirements

- Python 3.11+
- An [OpenRouter](https://openrouter.ai) API key (free tier available)

## Architecture

- **OpenRouter-native**: Uses the OpenAI SDK pointed at `https://openrouter.ai/api/v1`
- **Tool registry**: Self-registering tools with AST-based auto-discovery
- **Streaming**: Real-time token streaming with callbacks
- **Skills**: SKILL.md-based skill system for extensibility

## License

MIT
