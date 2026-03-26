import json
import os
import asyncio
from abc import ABC
from enum import Enum
from src.IConnectors import ILLMConnector, IImageConnector
from datetime import datetime
from fastapi.concurrency import run_in_threadpool

class AgentStatus(Enum):
    READY = "ready"
    BUSY = "busy"
    ERRORED = "errored"

class Agent(ABC):
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.last_response_time = 0
        self.status = AgentStatus.READY
        self.start_time = None

        self.last_response_file_path = None 

    def set_status(self, status: AgentStatus):
        self.status = status
        if status == AgentStatus.BUSY:
            self.start_time = datetime.now()
        elif status in [AgentStatus.READY, AgentStatus.ERRORED] and self.start_time:
            self.last_response_time = (datetime.now() - self.start_time).total_seconds()
            self.start_time = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "last_response_time": self.last_response_time
        }

class TextAgent(Agent):
    
    def __init__(self, id, name, system_prompt, connector: ILLMConnector):
        super().__init__(id, name)
        self.system_prompt = system_prompt
        self.connector = connector
        self.last_usage: dict | None = None  # populated after every call
        self.last_prompt = None
        self.last_response = None

    async def generate_text(self, prompt, temperature=0.7):
        self.set_status(AgentStatus.BUSY)
        self.last_prompt = prompt
        try:
            response, usage = await self.connector.chat(
                system_prompt=self.system_prompt,
                user_prompt=prompt,
                temperature=temperature
            )
            self.last_usage = usage
            self.last_response = response
            self.set_status(AgentStatus.READY)
            return response
        except Exception as e:
            print(f"Error generating text: {e}")
            self.set_status(AgentStatus.ERRORED)
            raise e

    async def generate_text_in_background(self, prompt, temperature=0.7):
        """Run generate_text in a threadpool for background, non-blocking execution."""
        self.set_status(AgentStatus.BUSY)
        def blocking_generate():
            self.last_prompt = prompt
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.connector.chat(
                    system_prompt=self.system_prompt,
                    user_prompt=prompt,
                    temperature=temperature
                ))
                return result
            except Exception as e:
                print(f"Error generating text (background): {e}")
                raise e
            finally:
                loop.close()
        try:
            response, usage = await run_in_threadpool(blocking_generate)
            self.last_usage = usage
            self.last_response = response
            self.set_status(AgentStatus.READY)
            return response
        except Exception as e:
            self.set_status(AgentStatus.ERRORED)
            raise e
        
    async def stream_text(self, prompt, temperature=0.7):
        self.set_status(AgentStatus.BUSY)
        self.last_prompt = prompt

        try:
            response = ""
            async for chunk in self.connector.stream(
                system_prompt=self.system_prompt,
                user_prompt=prompt,
                temperature=temperature
            ):
                if isinstance(chunk, dict):
                    # Final usage summary yielded by the connector — store it, don't yield it
                    self.last_usage = chunk
                elif chunk is not None:
                    response += chunk
                    yield chunk
            self.last_response = response
            self.set_status(AgentStatus.READY)
        except Exception as e:
            print(f"Error streaming text: {e}")
            self.set_status(AgentStatus.ERRORED)
            raise e

    def to_dict(self):
        d = super().to_dict()
        d["last_usage"] = self.last_usage
        return d

    def write_last_response_to_file(self, directory="./tmp"):
        self.last_response_file_path = os.path.join(directory, f"{self.name.replace(' ', '_')}_last_response.txt")
        if self.last_response:

            out = f"Agent Name: {self.name}\nPrompt:\n{self.last_prompt}\n\nResponse:\n{self.last_response}\n\nUsage:\n{json.dumps(self.last_usage, indent=2)}"
            os.makedirs(directory, exist_ok=True)
            with open(self.last_response_file_path, 'w', encoding='utf-8') as f:
                f.write(out)


class ImageAgent(Agent):
    def __init__(self, id, name, connector: IImageConnector):
        super().__init__(id, name)
        self.positive_keywords = ""
        self.negative_keywords = ""
        self.style = ""
        self.connector = connector

    async def generate_image(self, prompt, path, steps=15):
        from fastapi.concurrency import run_in_threadpool
        self.set_status(AgentStatus.BUSY)
        def blocking_generate():
            loop = asyncio.new_event_loop()
            try:
                full_prompt = f"{prompt}, {self.style}, {self.positive_keywords}"
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.connector.txt2img(full_prompt, self.negative_keywords, steps, path))
                return path
            except Exception as e:
                print(f"Error generating image (background): {e}")
                raise e
            finally:
                loop.close()
        try:
            result = await run_in_threadpool(blocking_generate)
            self.set_status(AgentStatus.READY)
            return result
        except Exception as e:
            self.set_status(AgentStatus.ERRORED)
            raise e