"""Minimal Anthropic Messages API client (plain httpx, no SDK). Swappable: the agent only needs `choose()`."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicClient:
    """Asks the model to answer by calling one tool, so the reply is structured and easy to check."""

    def __init__(self, model: str, max_tokens: int = 400, timeout_s: float = 30):
        load_dotenv(ROOT / ".env")
        self._key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model, self.max_tokens, self.timeout_s = model, max_tokens, timeout_s

    @property
    def available(self) -> bool:
        return bool(self._key)

    def choose(self, system: str, user: str, tool: dict) -> dict:
        """Return the arguments the model passed to `tool`. Raises on any API or format problem."""
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "tools": [tool], "tool_choice": {"type": "tool", "name": tool["name"]},
                "messages": [{"role": "user", "content": user}]}
        r = httpx.post(API_URL, json=body, timeout=self.timeout_s,
                       headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        for block in r.json().get("content", []):
            if block.get("type") == "tool_use":
                return block["input"]
        raise ValueError("the model did not return a decision")
