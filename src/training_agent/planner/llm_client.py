"""Minimal Anthropic Messages API client (plain httpx, no SDK). Swappable: the agent only needs `choose()`."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
MANUAL_DIR = ROOT / "data" / "llm"
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


class NoReply(Exception):
    """The manual client wrote its prompt and is waiting for a reply file (not an error)."""


class NullClient:
    """No language model: the plan stays rules-only."""

    available = False
    cacheable = False
    model = "none"


class ManualClient:
    """Copy-paste mode, no key needed. Each run writes data/llm/prompt_<day>.md; paste it into any chat model
    and save its JSON answer as data/llm/reply_<day>.json. The next run uses the reply (code still checks it)."""

    available = True
    cacheable = False  # the reply file is read fresh each time
    model = "manual"

    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory or MANUAL_DIR)

    def choose(self, system: str, user: str, tool: dict) -> dict:
        day = json.loads(user)["date"]
        self.dir.mkdir(parents=True, exist_ok=True)
        prompt = self.dir / f"prompt_{day}.md"
        reply = self.dir / f"reply_{day}.json"
        text = (f"{system}\n\nFacts for today (JSON):\n\n{user}\n\n"
                f"Reply with ONLY a JSON object like {{\"intensity\": \"easy\", \"coach_note\": \"2-3 sentences\"}}. "
                f"intensity must be one of {tool['input_schema']['properties']['intensity']['enum']} and not above the cap.\n")
        if not prompt.exists() or prompt.read_text() != text:
            prompt.write_text(text)
        if not reply.exists():
            raise NoReply(f"paste {prompt.name} into a chat model and save its answer as {reply}")
        match = re.search(r"\{.*\}", reply.read_text(), re.S)  # tolerate code fences or chatter around the JSON
        if not match:
            raise ValueError(f"{reply.name} has no JSON object")
        return json.loads(match.group(0))


def make_client(cfg: dict):
    """Pick the language-model client from config/llm.yaml: provider = manual (default) | anthropic | none."""
    provider = cfg.get("provider", "manual")
    if provider == "anthropic":
        return AnthropicClient(cfg.get("model", "claude-haiku-5-5"), cfg.get("max_tokens", 400), cfg.get("timeout_s", 30))
    if provider == "manual":
        return ManualClient()
    if provider == "none":
        return NullClient()
    raise ValueError(f"unknown LLM provider {provider!r} in config/llm.yaml (use manual, anthropic or none)")
