import json
from src.Memory import Memory

class Story():
    def __init__(self, directory: str):

        self.story_template_path = directory
        with open(f"{directory}/story.json", "r") as f:
            story_data = json.load(f)

        self.title = story_data.get("title", "Untitled Story")
        self.messages: list[Message] = []
        self.memory = Memory()
        self.turn_number = 0
        self.message_cutoff_index = 0
        self.last_time_est = 'STORY START, no time has passed yet'
        self.inventory = story_data.get("initial_inventory", "")

        self.base_plan = story_data.get("baseplan", "")
        self.base_plan_is_valid = bool(self.base_plan)

        self.config = story_data.get("config", {})

        self.messages.append(Message("System", story_data.get("initial_prompt", "")))
        

    def to_dict(self):
        return {
            "title": self.title,
            "story_template": self.story_template_path,
            "messages": [m.to_dict() for m in self.messages],
            "memory": self.memory.to_dict(),
            "turn_number": self.turn_number,
            "last_time_est": self.last_time_est,
            "inventory": self.inventory,
            "baseplan": self.base_plan,
            "base_plan_is_valid": self.base_plan_is_valid,
            "message_cutoff_index": self.message_cutoff_index

        }

    @classmethod
    def from_dict(cls, data):
        story = cls.__new__(cls)
        story.title = data.get("title", "Untitled Story")
        story.story_template_path = data.get("story_template", "")
        story.memory = Memory()
        story.memory.from_dict(data.get("memory", {}))
        story.turn_number = data.get("turn_number", 0)
        story.last_time_est = data.get("last_time_est", 'STORY START')
        story.inventory = data.get("inventory", "")
        story.base_plan = data.get("baseplan", "")
        story.base_plan_is_valid = data.get("base_plan_is_valid", bool(story.base_plan))
        story.message_cutoff_index = data.get("message_cutoff_index", 0)
        story.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return story

    def save(self, filename: str):

        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)
    
    def load(self, filename: str):
        with open(filename, 'r') as f:
            data = json.load(f)
            loaded_story = Story.from_dict(data)
            self.title = loaded_story.title
            self.story_template_path = loaded_story.story_template_path
            self.messages = loaded_story.messages
            self.memory = loaded_story.memory
            self.turn_number = loaded_story.turn_number
            self.last_time_est = loaded_story.last_time_est
            self.inventory = loaded_story.inventory
            self.message_cutoff_index = loaded_story.message_cutoff_index
            
            self.base_plan = loaded_story.base_plan
            self.base_plan_is_valid = loaded_story.base_plan_is_valid

class Message():
    def __init__(self, agent_name: str = "", content: str = ""):
        self.content = content
        self.agent_name = agent_name

    def to_dict(self):
        return {
            "agent_name": self.agent_name,
            "content": self.content
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            agent_name=data.get("agent_name", ""),
            content=data.get("content", "")
        )