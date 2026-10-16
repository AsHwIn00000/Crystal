from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class AIResponse:
    content: str
    model: str
    usage: dict  # {'prompt_tokens': int, 'completion_tokens': int}


# ── Error hierarchy ──────────────────────────────────────────────────────────

class AIProviderError(Exception):
    """Base class for all AI provider errors."""
    pass


class AIRateLimitError(AIProviderError):
    """Raised when the provider returns a rate-limit response (429).
    Callers should return HTTP 503 to the client and may retry after a delay."""
    pass


class AITimeoutError(AIProviderError):
    """Raised when the provider request times out.
    Callers should return HTTP 503 to the client."""
    pass


class AIAuthError(AIProviderError):
    """Raised when the API key is rejected (401/403).
    This is a fatal configuration error; callers should log CRITICAL and
    return HTTP 500 without exposing key details."""
    pass


class AIProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: List[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AIResponse:
        ...

    @abstractmethod
    def validate_model(self, model_id: str) -> bool:
        ...
