"""Provider-agnostic AI interface (spec §6: the model can be swapped)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str   # "system" | "user" | "assistant"
    content: str


@dataclass
class Completion:
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None


class AIProvider(ABC):
    """Minimal chat-completion contract any provider must satisfy."""

    @abstractmethod
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> Completion:
        ...
