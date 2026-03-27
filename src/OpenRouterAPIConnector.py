import os
import json
import requests
import httpx
from dotenv import load_dotenv
from src.IConnectors import ILLMConnector
load_dotenv()


class OpenRouterAPIConnector(ILLMConnector):

    API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    DONE_REASONS: tuple[str, ...] = ("stop", "length", "end_turn", "tool_calls", "content_filter")
    
    # Okay so I had many issues setting this up, and I need a real testbed of the openrouter API to
    # figure out what to do. But this works for deepseek, which has:
    # - Multiple providers, varies from $0.3/$0.5 to $0.6/$1.7
    # - Some with abysmal tps though (3-4), we want around ~20tps
    # - These two providers seem to give cheap but fast stats, so for now, we'll keep them

    def __init__(self, _api_key: str):
        self._api_key: str = _api_key
        self._model: str = 'deepseek/deepseek-v3.2'
        self._context_length: int = 64_000
        self._providers = { 'only': ['novita', 'atlas-cloud'] }

    def _get_header(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

    def _get_payload(self, system_prompt: str, user_prompt: str, temperature: float) -> dict:
        return {
            "model": self._model,
            "messages":  [{
                "role": "system",
                "content": system_prompt
            }, {
                "role": "user",
                "content": user_prompt
            }],
            "temperature": temperature,
            "provider": self._providers
        }

    def get_max_context_length(self) -> int:
        return self._context_length
    
    def get_api_name(self) -> str:
        return f'OpenRouter ({self._model})'

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> tuple[str, dict]:
        headers = self._get_header()
        payload = self._get_payload(system_prompt, user_prompt, temperature)
        response = requests.post(OpenRouterAPIConnector.API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_usage = data.get("usage", {})
        usage = self._format_usage(raw_usage)
        return content, usage

    async def stream(self, system_prompt: str, user_prompt: str, temperature: float = 0.7):
        headers = self._get_header()
        payload = self._get_payload(system_prompt, user_prompt, temperature)
        payload['stream'] = True
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
    
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", OpenRouterAPIConnector.API_URL, headers=headers, json=payload) as response:
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
                        print(f"Failed to parse JSON chunk: {e}")
                        continue
    
                    choice = data.get("choices", [{}])[0]
                    finish_reason = choice.get("finish_reason")
                    content = choice.get("delta", {}).get("content")
    
                    if content:
                        yield content
    
                    if finish_reason in OpenRouterAPIConnector.DONE_REASONS:
                        yield None
