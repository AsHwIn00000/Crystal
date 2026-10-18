import re
import time
import logging
from groq import Groq, RateLimitError, APITimeoutError, AuthenticationError, APIError
from app.ai.base_provider import (
    AIProvider, AIResponse,
    AIProviderError, AIRateLimitError, AITimeoutError, AIAuthError,
)

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict = {}  # model_id -> (valid: bool, timestamp: float)
_MODEL_CACHE_TTL = 3600  # 1 hour
FALLBACK_MODELS = ['openai/gpt-oss-120b']


class GroqProvider(AIProvider):
    def __init__(self, api_key: str, model_id: str):
        if not api_key:
            raise ValueError('GROQ_API_KEY is not set.')
        self.client = Groq(api_key=api_key)
        self.model_id = model_id

    def _execute_completion(self, model: str, messages: list, max_tokens: int, temperature: float) -> AIResponse:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=45.0
        )
        content = response.choices[0].message.content or ''
        # Strip <think>...</think> blocks that reasoning models emit
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

    def chat(self, messages: list, max_tokens: int = 2048, temperature: float = 0.7) -> AIResponse:
        # Try primary model first, with automatic retry on rate-limit/overload
        models_to_try = [self.model_id] + [m for m in FALLBACK_MODELS if m != self.model_id]

        last_error = None
        for i, model in enumerate(models_to_try):
            for attempt in range(2):
                try:
                    return self._execute_completion(model, messages, max_tokens, temperature)
                except RateLimitError as exc:
                    last_error = exc
                    logger.warning('Groq RateLimit on model %s (attempt %d). Retrying...', model, attempt + 1)
                    time.sleep(1.2)  # Brief pause before retry or fallback
                except APITimeoutError as exc:
                    last_error = exc
                    logger.warning('Groq Timeout on model %s. Trying fallback...', model)
                    break
                except AuthenticationError as exc:
                    raise AIAuthError('AI service authentication failed.') from exc
                except APIError as exc:
                    last_error = exc
                    logger.error('Groq APIError [%s] on model %s: %s', type(exc).__name__, model, exc)
                    break
                except Exception as exc:
                    last_error = exc
                    logger.error('Unexpected error on model %s: %s', model, exc)
                    break

        if isinstance(last_error, RateLimitError):
            raise AIRateLimitError('The AI service is busy. Please try again in a moment.') from last_error
        elif isinstance(last_error, APITimeoutError):
            raise AITimeoutError('Request timed out. Please try again.') from last_error
        elif last_error:
            raise AIProviderError(f'AI service error: {str(last_error)}') from last_error

        raise AIProviderError('Unable to generate response from any available AI model.')

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
