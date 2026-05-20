"""Elitza Agent -- Core agent loop with tool calling.

Inspired by Hermes Agent's run_agent.py but simplified:
- OpenRouter only (no provider abstraction)
- CLI only (no gateway/TUI)
- Essential tools only (expandable via registry)
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from elitza.constants import OPENROUTER_BASE_URL, get_elitza_home
from elitza.tools import registry

logger = logging.getLogger(__name__)


class ElitzaAgent:
    """AI agent with OpenRouter-native tool calling."""

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        base_url: str = OPENROUTER_BASE_URL,
        max_iterations: int = 50,
        system_prompt: str = "",
        enabled_toolsets: Optional[List[str]] = None,
        disabled_toolsets: Optional[List[str]] = None,
        verbose: bool = False,
    ):
        self.model = model or "anthropic/claude-sonnet-4"
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt
        self.enabled_toolsets = enabled_toolsets
        self.disabled_toolsets = disabled_toolsets
        self.verbose = verbose

        # OpenAI client pointed at OpenRouter
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            base_url=base_url,
        )

        # Tool schemas for the current session
        self.tools = registry.get_openai_schemas(enabled_toolsets, disabled_toolsets)

        # Session state
        self.session_id = str(uuid.uuid4())[:12]
        self.messages: List[Dict[str, Any]] = []
        self._cached_system_prompt: Optional[str] = None

    def _build_system_prompt(self) -> str:
        """Build the system prompt."""
        if self._cached_system_prompt:
            return self._cached_system_prompt

        parts = []

        # Base identity
        if self.system_prompt:
            parts.append(self.system_prompt)
        else:
            parts.append(self._default_system_prompt())

        # Tool count info
        tool_count = len(self.tools)
        parts.append(f"\nYou have access to {tool_count} tools.")

        self._cached_system_prompt = "\n\n".join(parts)
        return self._cached_system_prompt

    def _default_system_prompt(self) -> str:
        return """You are Elitza, an AI agent built for the Elitza Ecosystem.
You are direct, efficient, and helpful. You use tools to accomplish tasks.
You think step by step and explain your reasoning when it helps.
You are running in a CLI environment."""

    def run(
        self,
        user_message: str,
        stream: bool = True,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Run a conversation turn with tool calling until completion.

        Args:
            user_message: The user's input
            stream: Whether to stream the response
            on_token: Optional callback for each token during streaming

        Returns:
            The final text response
        """
        # Add user message
        self.messages.append({"role": "user", "content": user_message})

        system_prompt = self._build_system_prompt()
        final_response = ""

        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\n[Iteration {iteration + 1}/{self.max_iterations}]", file=sys.stderr)

            # Build API messages
            api_messages = [{"role": "system", "content": system_prompt}] + self.messages

            # Call the model
            try:
                if stream:
                    response_text, tool_calls = self._call_streaming(
                        api_messages, on_token
                    )
                else:
                    response_text, tool_calls = self._call_non_streaming(api_messages)
            except Exception as e:
                logger.error("API call failed: %s", e)
                return f"Error: {e}"

            # If no tool calls, we're done
            if not tool_calls:
                final_response = response_text
                self.messages.append({
                    "role": "assistant",
                    "content": response_text,
                })
                break

            # Add assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": response_text or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tool_calls
                ],
            }
            self.messages.append(assistant_msg)

            # Execute tool calls
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                if self.verbose:
                    print(f"  Tool: {name}({json.dumps(args, default=str)[:100]})", file=sys.stderr)

                result = registry.dispatch(name, args)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                })

                if self.verbose:
                    preview = str(result)[:200]
                    print(f"  Result: {preview}", file=sys.stderr)

        return final_response

    def _call_streaming(
        self,
        messages: List[Dict],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> tuple:
        """Call OpenRouter with streaming. Returns (text, tool_calls)."""
        response_text = ""
        tool_calls: List[Dict] = []
        current_tool: Optional[Dict] = None

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "auto"

        stream = self.client.chat.completions.create(**kwargs)

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Text content
            if delta.content:
                response_text += delta.content
                if on_token:
                    on_token(delta.content)

            # Tool calls (streamed incrementally)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    # Extend list if needed
                    while len(tool_calls) <= idx:
                        tool_calls.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    if tc_delta.id:
                        tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls[idx]["function"]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

        return response_text, tool_calls

    def _call_non_streaming(self, messages: List[Dict]) -> tuple:
        """Call OpenRouter without streaming. Returns (text, tool_calls)."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if self.tools:
            kwargs["tools"] = self.tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        text = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        return text, tool_calls
