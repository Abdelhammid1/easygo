"""DeepSeek provider (OpenAI-compatible chat completions API)."""
from __future__ import annotations

import requests
from flask import current_app

from app.services.ai.base import AIProvider, ChatMessage, Completion

# Rough public pricing (USD per 1M tokens) for cost estimation only (spec §6.5).
# Update if DeepSeek pricing changes; used for reporting, not billing.
_PRICE_PER_MTOK = {
    "deepseek-chat": {"in": 0.27, "out": 1.10},
    "deepseek-reasoner": {"in": 0.55, "out": 2.19},
}


class DeepSeekProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> Completion:
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured")

        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        timeout = current_app.config.get("HTTP_TIMEOUT", 30)
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        p_tok = usage.get("prompt_tokens")
        c_tok = usage.get("completion_tokens")
        return Completion(
            content=content,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            cost_usd=self._estimate_cost(p_tok, c_tok),
        )

    def _estimate_cost(self, p_tok, c_tok) -> float | None:
        price = _PRICE_PER_MTOK.get(self.model)
        if not price or p_tok is None or c_tok is None:
            return None
        return round((p_tok * price["in"] + c_tok * price["out"]) / 1_000_000, 6)
