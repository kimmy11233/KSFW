import os
import json
from src.Agent import TextAgent, ImageAgent
import re



class SystemPromptCompiler:

    def __init__(self, ):
        self.data_registry: dict[str, str] = {}
        self.image_prompt_config: dict[str, str] = {}

    def import_system_prompt(self, path: str):
        # Add all markdown files in the folder to the data registry
        for filename in os.listdir(path):
            if filename.endswith('.md'):
                file_path = os.path.join(path, filename)
                with open(file_path, 'r', encoding='utf-8') as md_file:
                    content = md_file.read()
                    key = os.path.splitext(filename)[0]
                    self.data_registry[key] = content

        print(f"Imported system prompts from '{path}':")

        image_agent_json_path = os.path.join(path, "image_agent.json")
        if os.path.isfile(image_agent_json_path):
            with open(image_agent_json_path, 'r', encoding='utf-8') as json_file:
                self.image_prompt_config = json.load(json_file)

        default_path = "./Default System Prompts"
        if os.path.isdir(default_path):
            for filename in os.listdir(default_path):
                if filename.endswith('.md'):
                    key = os.path.splitext(filename)[0]
                    # Only add if not already in data_registry
                    if key not in self.data_registry:
                        file_path = os.path.join(default_path, filename)
                        with open(file_path, 'r', encoding='utf-8') as md_file:
                            content = md_file.read()
                            self.data_registry[key] = content
            
            print(f"Loaded default system prompts from '{default_path}'")

    def compile_system_prompt(self, agent: TextAgent | ImageAgent, system_prompt_lookup: str) -> None:
        if isinstance(agent, ImageAgent):
            positive_keywords = self.image_prompt_config.get("Positive_Keywords", "")
            negative_keywords = self.image_prompt_config.get("Negative_Keywords", "")
            style = self.image_prompt_config.get("Style", "")
            
            agent.positive_keywords = positive_keywords
            agent.negative_keywords = negative_keywords
            agent.style = style
            
            print(f"Compiled image prompt for agent '{agent.name}':")
            return
        
        elif isinstance(agent, TextAgent):
            # For TextAgents, we can simply return the system prompt from the data registry
            prompt_template = self.data_registry.get(system_prompt_lookup, None)
            if prompt_template is not None:
                required_lookups = re.findall(r'<input>([^<]+)</input>', prompt_template)

                for lookup in required_lookups:
                    if lookup in self.data_registry:
                        prompt_template = prompt_template.replace(f"{{{lookup}}}", self.data_registry[lookup])
                    else:
                        raise ValueError(f"Required system prompt '{lookup}' not found in data registry for '{system_prompt_lookup}'.")

                agent.system_prompt = prompt_template
                return
            else:
                raise ValueError(f"System prompt '{system_prompt_lookup}' not found in data registry.")
        
        else:
            raise TypeError("Unsupported agent type for system prompt compilation.")