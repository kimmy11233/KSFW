from abc import ABC, abstractmethod

class ILLMConnector(ABC):
    @abstractmethod
    async def chat(self, system_prompt, user_prompt, temperature):
        pass

    @abstractmethod
    async def stream(self, system_prompt, user_prompt, temperature):
        pass

    @abstractmethod
    def get_max_context_length(self) -> int:
        """Return the max context window in tokens for the current model."""
        pass

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
    async def txt2img(self, prompt, negative_prompt, steps, path):
        pass