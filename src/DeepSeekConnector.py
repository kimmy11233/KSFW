import os
import json
import httpx
import logging
import requests
from dotenv import load_dotenv
from src.IConnectors import ILLMConnector
load_dotenv()
logger = logging.getLogger(__name__)
DONE_REASONS = ("stop", "length", "end_turn", "tool_calls", "content_filter", "insufficient_system_resource")

# Model context windows — update if DeepSeek releases new models
DEEPSEEK_CONTEXT_LENGTHS = {
    "deepseek-chat": 64000,
    "deepseek-reasoner": 64000,
}

class DeepSeekAPIConnector(ILLMConnector):
    def __init__(self, api_key: str, model="deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

    def get_max_context_length(self) -> int:
        """Return the max context window in tokens for the current model."""
        return DEEPSEEK_CONTEXT_LENGTHS.get(self.model, 64000)
    
    def get_api_name(self) -> str:
        return f'DeepSeek ({self.model})'

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _payload(self, system_prompt: str, user_prompt: str, temperature: float, stream: bool = False):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "stream": stream,
            "stream_options": {"include_usage": True} if stream else None
        }

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> tuple[str, dict]:
        """
        Returns (content, usage) where usage is:
          {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "context_pct": float}
        """
        response = requests.post(
            self.DEEPSEEK_API_URL,
            headers=self._headers(),
            json=self._payload(system_prompt, user_prompt, temperature)
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_usage = data.get("usage", {})
        usage = self._format_usage(raw_usage)
        return content, usage

    async def stream(self, system_prompt: str, user_prompt: str, temperature: float = 0.7):
        """
        Yields str chunks during streaming, then yields a final dict with usage info:
          {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "context_pct": float}
        Callers should check: if isinstance(chunk, dict): # it's the usage summary
        """
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                self.DEEPSEEK_API_URL,
                headers=self._headers(),
                json=self._payload(system_prompt, user_prompt, temperature, stream=True)
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    decoded_line = line.strip()
                    if decoded_line.startswith("event: "):
                        continue
                    elif decoded_line.startswith(":"):
                        continue
                    elif decoded_line == "data: [DONE]":
                        continue
                    elif decoded_line.startswith("data: "):
                        decoded_line = decoded_line[len("data: "):]
                    else:
                        continue
                    try:
                        data = json.loads(decoded_line)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse JSON chunk", extra={"raw": decoded_line, "error": str(e)})
                        continue
                    choice = data.get("choices", [{}])[0]
                    finish_reason = choice.get("finish_reason")
                    content = choice.get("delta", {}).get("content")
                    if content:
                        yield content
                    if finish_reason in DONE_REASONS:
                        if finish_reason == "insufficient_system_resource":
                            logger.warning("DeepSeek stream ended due to insufficient system resources")
                    # Usage comes on the final chunk (stream_options: include_usage)
                    raw_usage = data.get("usage")
                    if raw_usage:
                        usage = self._format_usage(raw_usage)
                        logger.info("Stream complete", extra={"usage": usage})
                        yield usage  # final yield is a dict, not a str
