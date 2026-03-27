from abc import ABC, abstractmethod
from typing import AsyncGenerator

class ILLMConnector(ABC):

    @abstractmethod
    async def chat(self, system_prompt: str, user_prompt: str, temperature: float) -> tuple[str, dict]:
        pass

    @abstractmethod
    async def stream(self, system_prompt: str, user_prompt: str, temperature: float) -> AsyncGenerator[str | dict | None, None]:
        yield None

    @abstractmethod
    def get_max_context_length(self) -> int:
        """Return the max context window in tokens for the current model."""
        pass

    @abstractmethod
    def get_api_name(self) -> str:
        """ Return the name of the API used, to display in the UI """
        return ''

    def _format_usage(self, raw_usage: dict) -> dict:
        """Normalise usage dict and append context_pct."""
        prompt_tokens = raw_usage.get("prompt_tokens", 0)
        completion_tokens = raw_usage.get("completion_tokens", 0)
        total_tokens = raw_usage.get("total_tokens", prompt_tokens + completion_tokens)
        max_ctx = self.get_max_context_length()
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "context_pct": round(total_tokens / max_ctx * 100, 1) if max_ctx else 0.0,
        }

class IImageConnector(ABC):
    @abstractmethod
    async def txt2img(self, prompt: str, negative_prompt: str, steps: int, path: str) -> str:
        pass