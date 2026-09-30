from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResult:
    text: str
    provider: str          # "keygateway" | "local" | "deterministic"
    model_used: Optional[str]
    fallback_used: bool
    fallback_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    raw: Optional[dict] = field(default=None, repr=False)


class LLMProvider(ABC):
    """Anything that can turn a prompt into text. Implementations must
    never raise for "the vendor is down" -- that's what LLMProviderChain
    (fallback.py) is for. A provider should raise only for programmer
    errors (bad config); transient/vendor failures are caught and
    surfaced via a `ProviderCallFailed` exception so the chain can move on.
    """

    name: str = "base"

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2, max_tokens: int = 800) -> LLMResult:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...


class ProviderCallFailed(Exception):
    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider} failed: {reason}")
        self.provider = provider
        self.reason = reason
