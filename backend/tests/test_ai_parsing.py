"""AI reply robustness (ticket §1 acceptance): tolerant parsing + blank-retry."""
from app.services.ai.base import AIProvider, ChatMessage, Completion
from app.services.ai.service import (
    MAX_MODEL_ATTEMPTS,
    _coerce_decision_dict,
    _extract_json,
    _run_model,
    _PLAINTEXT_CONFIDENCE,
)


class FakeProvider(AIProvider):
    """Returns a scripted list of contents; records the json_mode of each call."""

    def __init__(self, contents, raise_on=None):
        self._contents = list(contents)
        self.json_modes: list[bool] = []
        self._raise_on = raise_on

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False,
                 temperature: float = 0.3) -> Completion:
        idx = len(self.json_modes)
        self.json_modes.append(json_mode)
        if self._raise_on is not None and idx == self._raise_on:
            raise RuntimeError("boom")
        return Completion(content=self._contents[idx], finish_reason="stop")


def test_extract_json_direct_fenced_embedded():
    direct = _extract_json('{"reply":"hi"}')
    fenced = _extract_json('```json\n{"reply":"hi"}\n```')
    embedded = _extract_json('سيبها كده {"reply":"hi"} خلاص')
    braces = _extract_json('{"reply":"a {b} c"}')  # braces inside a string value
    assert direct and direct["reply"] == "hi"
    assert fenced and fenced["reply"] == "hi"
    assert embedded and embedded["reply"] == "hi"
    assert braces and braces["reply"] == "a {b} c"
    assert _extract_json("no json here") is None


def test_coerce_prose_fallback_confidence():
    d = _coerce_decision_dict("أهلاً بيك، اتفضل اطلب")
    assert d is not None
    assert d["reply"] == "أهلاً بيك، اتفضل اطلب"
    assert d["confidence"] == _PLAINTEXT_CONFIDENCE
    assert d["escalate"] is False
    assert _coerce_decision_dict("   ") is None
    assert _coerce_decision_dict("") is None


def test_retry_recovers_on_third_attempt():
    # Blank, whitespace, then valid JSON (ticket §1 acceptance).
    provider = FakeProvider(["", "   ", '{"reply":"تمام","confidence":0.8}'])
    result = _run_model(provider, [])
    assert result.parsed is not None
    assert result.parsed["reply"] == "تمام"
    assert result.attempts == 3
    # First attempt uses strict JSON, retries drop response_format.
    assert provider.json_modes == [True, False, False]


def test_all_blank_yields_no_parse():
    provider = FakeProvider(["", "   ", "\n"])
    result = _run_model(provider, [])
    assert result.parsed is None
    assert result.attempts == MAX_MODEL_ATTEMPTS
    assert result.error is None  # blank, not an exception


def test_provider_exception_reported():
    provider = FakeProvider(["ignored"], raise_on=0)
    result = _run_model(provider, [])
    assert result.parsed is None
    assert result.error == "boom"
