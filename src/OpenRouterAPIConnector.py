import os
import json
import requests
import httpx
from dotenv import load_dotenv
from src.IConnectors import ILLMConnector
load_dotenv()


DONE_REASONS = ("stop", "length", "end_turn", "tool_calls", "content_filter")
class OpenRouterAPIConnector(ILLMConnector):

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def get_max_context_length(self) -> int:
        return 64000  # As long as we don't change the underlying model, it's still deepseek

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> tuple[str, dict]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": 'deepseek/deepseek-v3.2',
            "messages":  [{
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }],
            "temperature": temperature
        }

        response = requests.post(self.OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_usage = data.get("usage", {})
        usage = self._format_usage(raw_usage)
        return content, usage

    async def stream(self, system_prompt: str, user_prompt: str, temperature: float = 0.7):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": 'deepseek/deepseek-v3.2',
            "messages":  [{
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }],
            "stream": True,
            "temperature": temperature
        }
 
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
    
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", self.OPENROUTER_API_URL, headers=headers, json=payload) as response:
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
                        print("Failed to parse JSON chunk")
                        continue
    
                    choice = data.get("choices", [{}])[0]
                    finish_reason = choice.get("finish_reason")
                    content = choice.get("delta", {}).get("content")
    
                    if content:
                        yield content
    
                    if finish_reason in DONE_REASONS:
                        yield None
    