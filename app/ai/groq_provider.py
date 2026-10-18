import re
import time
import logging
from groq import Groq, RateLimitError, APITimeoutError, AuthenticationError, APIError
from app.ai.base_provider import (
    AIProvider, AIResponse,
    AIProviderError, AIRateLimitError, AITimeoutError, AIAuthError,
)

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict = {}  # model_id → (valid: bool, timestamp: float)
_MODEL_CACHE_TTL = 3600  # 1 hour


class GroqProvider(AIProvider):
    def __init__(self, api_key: str, model_id: str):
        if not api_key:
            raise ValueError('GROQ_API_KEY is not set.')
        self.client = Groq(api_key=api_key)
        self.model_id = model_id

    def chat(self, messages: list, max_tokens: int = 2048, temperature: float = 0.7) -> AIResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60.0
            )
            content = response.choices[0].message.content or ''
            # Strip <think>...</think> blocks that qwen/reasoning models emit
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            if not content:
                content = 'I was unable to generate a response. Please try again.'
            return AIResponse(
                content=content,
                model=response.model,
                usage={
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens
                }
            )
        except RateLimitError as exc:
            raise AIRateLimitError('Rate limit reached. Please try again in a moment.') from exc
        except APITimeoutError as exc:
            raise AITimeoutError('Request timed out. Please try again.') from exc
        except AuthenticationError as exc:
            raise AIAuthError('AI service authentication failed.') from exc
        except APIError as exc:
            # Includes NotFoundError (model not found), BadRequestError, etc.
            logger.error('Groq APIError [%s]: %s', type(exc).__name__, exc)
            raise AIProviderError(f'AI service error ({type(exc).__name__}): {str(exc)}') from exc
        except Exception as exc:
            logger.error('Unexpected Groq error [%s]: %s', type(exc).__name__, exc)
            raise AIProviderError(f'Unexpected AI error: {str(exc)}') from exc

    def validate_model(self, model_id: str) -> bool:
        """Check model availability with 1-hour result cache. Returns False (not raises) on errors."""
        now = time.monotonic()
        cached = _MODEL_CACHE.get(model_id)
        if cached and (now - cached[1]) < _MODEL_CACHE_TTL:
            return cached[0]
        try:
            models = self.client.models.list()
            valid = any(m.id == model_id for m in models.data)
        except Exception as exc:
            logger.warning('validate_model: could not reach Groq models API: %s', exc)
            valid = True  # Non-fatal: assume valid if unreachable
        _MODEL_CACHE[model_id] = (valid, now)
        return valid
