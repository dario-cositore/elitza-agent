"""Elitza Agent CLI -- Interactive terminal interface.

Usage:
    elitza                    # Start interactive mode
    elitza setup              # Run setup wizard
    elitza --model <model>    # Use a specific model
    elitza -m "message"       # Single message mode
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from elitza.constants import get_elitza_home, get_config_path, get_env_path, OPENROUTER_BASE_URL
from elitza.agent import ElitzaAgent


def load_config() -> dict:
    """Load config from ~/.elitza/config.yaml and .env."""
    env_path = get_env_path()
    if env_path.exists():
        load_dotenv(env_path)

    import yaml
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def build_agent(args: argparse.Namespace, config: dict) -> ElitzaAgent:
    """Build an ElitzaAgent from args and config."""
    from elitza.tools import discover_tools, registry as _
    discover_tools()

    model = args.model or config.get("model", "")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = OPENROUTER_BASE_URL

    system_prompt = config.get("system_prompt", "")
    max_iterations = config.get("max_iterations", 50)

    enabled = None
    disabled = None
    if args.toolsets:
        enabled = [t.strip() for t in args.toolsets.split(",")]

    return ElitzaAgent(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_iterations=max_iterations,
        system_prompt=system_prompt,
        enabled_toolsets=enabled,
        disabled_toolsets=disabled,
        verbose=args.verbose,
    )


def interactive_loop(agent: ElitzaAgent):
    """Run the interactive REPL."""
    print("Elitza Agent v0.1.0 -- OpenRouter native")
    print(f"Model: {agent.model}")
    print(f"Session: {agent.session_id}")
    print("Type 'quit' or 'exit' to end. Ctrl+C to interrupt.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        print("Elitza: ", end="", flush=True)

        def on_token(token: str):
            print(token, end="", flush=True)

        try:
            result = agent.run(user_input, stream=True, on_token=on_token)
            print()
        except KeyboardInterrupt:
            print("\n[interrupted]")
            continue
        except Exception as e:
            print(f"\n[error: {e}]")
            if agent.verbose:
                import traceback
                traceback.print_exc()
            continue


def single_message(agent: ElitzaAgent, message: str):
    """Process a single message and print the result."""
    def on_token(token: str):
        print(token, end="", flush=True)

    result = agent.run(message, stream=True, on_token=on_token)
    print()


# ============================================================================
# Setup Wizard
# ============================================================================

def run_setup_wizard():
    """Interactive setup wizard for first-time configuration."""
    elitza_home = get_elitza_home()
    env_path = get_env_path()
    config_path = get_config_path()

    print("")
    print("=" * 50)
    print("  Elitza Agent Setup Wizard")
    print("=" * 50)
    print("")

    # --- Step 1: OpenRouter API Key ---
    print("Step 1: OpenRouter API Key")
    print("-" * 30)
    print("Elitza uses OpenRouter to access AI models.")
    print("Get your free API key at: https://openrouter.ai/keys")
    print("")

    current_key = os.environ.get("OPENROUTER_API_KEY", "")
    if current_key:
        masked = current_key[:8] + "..." + current_key[-4:]
        print(f"Current key: {masked}")
        change = input("Change API key? [y/N] ").strip().lower()
        if change != "y":
            print("Keeping existing key.")
        else:
            current_key = ""
    else:
        current_key = ""

    if not current_key:
        api_key = input("Enter your OpenRouter API key: ").strip()
        if not api_key:
            print("No key entered. You can add it later to ~/.elitza/.env")
            api_key = ""
    else:
        api_key = current_key

    # --- Step 2: Default Model ---
    print("")
    print("Step 2: Default Model")
    print("-" * 30)
    print("Which model would you like to use by default?")
    print("")
    print("  1. anthropic/claude-sonnet-4    (recommended)")
    print("  2. anthropic/claude-opus-4      (most capable)")
    print("  3. openai/gpt-4o                (fast, reliable)")
    print("  4. google/gemini-2.5-pro        (Google's best)")
    print("  5. deepseek/deepseek-chat       (great value)")
    print("  6. Custom (enter model ID)")
    print("")

    model_map = {
        "1": "anthropic/claude-sonnet-4",
        "2": "anthropic/claude-opus-4",
        "3": "openai/gpt-4o",
        "4": "google/gemini-2.5-pro",
        "5": "deepseek/deepseek-chat",
    }

    choice = input("Choose [1-6, default=1]: ").strip()
    if not choice:
        choice = "1"

    if choice in model_map:
        model = model_map[choice]
    elif choice == "6":
        model = input("Enter OpenRouter model ID: ").strip()
        if not model:
            model = "anthropic/claude-sonnet-4"
    else:
        model = "anthropic/claude-sonnet-4"

    print(f"Selected: {model}")

    # --- Step 3: System Prompt (optional) ---
    print("")
    print("Step 3: Custom System Prompt (optional)")
    print("-" * 30)
    print("You can set a custom system prompt to change Elitza's behavior.")
    print("Leave empty for the default prompt.")
    print("")

    custom_prompt = input("Custom system prompt (or Enter to skip): ").strip()

    # --- Write .env ---
    print("")
    print("Writing configuration...")

    elitza_home.mkdir(parents=True, exist_ok=True)

    env_content = "# Elitza Agent Environment Variables\n"
    env_content += "# Generated by elitza setup\n\n"
    if api_key:
        env_content += f"OPENROUTER_API_KEY={api_key}\n"
    else:
        env_content += "# OPENROUTER_API_KEY=your-key-here\n"

    env_path.write_text(env_content, encoding="utf-8")
    print(f"  Created: {env_path}")

    # --- Write config.yaml ---
    import yaml
    config = {
        "model": model,
        "max_iterations": 50,
    }
    if custom_prompt:
        config["system_prompt"] = custom_prompt

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"  Created: {config_path}")

    # --- Verify ---
    print("")
    print("Verifying setup...")

    # Reload env
    load_dotenv(env_path)
    verify_key = os.environ.get("OPENROUTER_API_KEY", "")

    if verify_key:
        print("  API key: OK")
    else:
        print("  API key: NOT SET (run 'elitza setup' to add it)")

    print(f"  Model: {model}")
    print(f"  Config: {config_path}")

    # --- Test connection ---
    print("")
    test = input("Test connection to OpenRouter now? [Y/n] ").strip().lower()
    if test != "n":
        print("Testing...")
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=verify_key,
                base_url=OPENROUTER_BASE_URL,
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with 'OK' to confirm the connection works."}],
                max_tokens=20,
            )
            reply = resp.choices[0].message.content
            print(f"  Connection successful! Model replied: {reply}")
        except Exception as e:
            print(f"  Connection test failed: {e}")
            print("  You can retry later with: elitza setup")

    # --- Done ---
    print("")
    print("=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print("")
    print("Start using Elitza:")
    print("  elitza              # Interactive mode")
    print("  elitza -m \"hello\"   # Single message")
    print("  elitza --help       # Full help")
    print("")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Elitza Agent -- OpenRouter-native AI agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  elitza              # Interactive mode\n  elitza setup        # Configure API key and model\n  elitza -m \"hello\"   # Single message\n",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Setup subcommand
    setup_parser = subparsers.add_parser("setup", help="Run the setup wizard")
    setup_parser.add_argument("--api-key", default="", help="OpenRouter API key (skip interactive)")
    setup_parser.add_argument("--model", default="", help="Default model ID")

    # Main options
    parser.add_argument("-m", "--message", help="Single message mode (non-interactive)")
    parser.add_argument("--model", default="", help="Model to use (e.g. anthropic/claude-sonnet-4)")
    parser.add_argument("--toolsets", default="", help="Comma-separated toolsets to enable")
    parser.add_argument("--list-tools", action="store_true", help="List available tools and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Handle subcommands
    if args.command == "setup":
        if args.api_key or args.model:
            # Non-interactive setup
            _non_interactive_setup(args)
        else:
            run_setup_wizard()
        return

    config = load_config()

    # List tools mode
    if args.list_tools:
        from elitza.tools import discover_tools, registry
        discover_tools()
        tools = registry.get_all_tools()
        print(f"Available tools ({len(tools)}):")
        for name, entry in sorted(tools.items()):
            print(f"  {name:20s} [{entry.toolset:10s}] {entry.description}")
        return

    agent = build_agent(args, config)

    if args.message:
        single_message(agent, args.message)
    else:
        interactive_loop(agent)


def _non_interactive_setup(args: argparse.Namespace):
    """Non-interactive setup for scripted installs."""
    elitza_home = get_elitza_home()
    env_path = get_env_path()
    config_path = get_config_path()

    elitza_home.mkdir(parents=True, exist_ok=True)

    # Write .env
    env_content = "# Elitza Agent Environment Variables\n"
    if args.api_key:
        env_content += f"OPENROUTER_API_KEY={args.api_key}\n"
    else:
        env_content += "# OPENROUTER_API_KEY=your-key-here\n"

    env_path.write_text(env_content, encoding="utf-8")
    print(f"Created: {env_path}")

    # Write config.yaml
    import yaml
    model = args.model or "anthropic/claude-sonnet-4"
    config = {"model": model, "max_iterations": 50}
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"Created: {config_path}")

    print("Setup complete. Run 'elitza' to start.")


if __name__ == "__main__":
    main()
