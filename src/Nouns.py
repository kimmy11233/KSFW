from enum import Enum
from typing import Optional, Union
from src.Agent import Agent
import json
import os

class NounType(Enum):
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"

class Noun_Repository():
    def __init__(self):
        self.factions: dict[str, Faction] = {}
        self.characters: dict[str, Character] = {}
        self.locations: dict[str, Location] = {}
        self.items: dict[str, Item] = {}

    def to_dict(self):
        return {
            "factions": {key: self.factions[key].to_dict() for key in self.factions},
            "characters": {key: self.characters[key].to_dict() for key in self.characters},
            "locations": {key: self.locations[key].to_dict() for key in self.locations},
            "items": {key: self.items[key].to_dict() for key in self.items},
        }
    
    @staticmethod
    def from_dict(data: dict):
        repo = Noun_Repository()
        for key in data.get("factions", {}):
            repo.factions[key] = Faction.from_response(data["factions"][key])
        for key in data.get("characters", {}):
            repo.characters[key] = Character.from_response(data["characters"][key])
        for key in data.get("locations", {}):
            repo.locations[key] = Location.from_response(data["locations"][key])
        for key in data.get("items", {}):
            repo.items[key] = Item.from_response(data["items"][key])
        return repo

    def get(self, key: str) -> Optional[Union['Faction', 'Character', 'Location', 'Item']]:
        if key in self.factions:
            return self.factions[key]
        elif key in self.characters:
            return self.characters[key]
        elif key in self.locations:
            return self.locations[key]
        elif key in self.items:
            return self.items[key]
        else:
            return None

    def __getitem__(self, key):
        if key in self.factions:
            return self.factions[key]
        elif key in self.characters:
            return self.characters[key]
        elif key in self.locations:
            return self.locations[key]
        elif key in self.items:
            return self.items[key]
        else:
            raise KeyError(f"Noun with name '{key}' not found in repository.")
        
    def __setitem__(self, key, value):
        if isinstance(value, Faction):
            self.factions[key] = value
        elif isinstance(value, Character):
            self.characters[key] = value
        elif isinstance(value, Location):
            self.locations[key] = value
        elif isinstance(value, Item):
            self.items[key] = value
        else:
            raise ValueError(f"Value must be an instance of Faction, Character, Location, or Item. Got {type(value)} instead.")
        
    def delete_noun(self, key):
        if key in self.factions:
            del self.factions[key]
        elif key in self.characters:
            del self.characters[key]
        elif key in self.locations:
            del self.locations[key]
        elif key in self.items:
            del self.items[key]
        else:
            raise KeyError(f"Noun with name '{key}' not found in repository.")

def _noun_from_data(data: dict):
    """Dispatch a raw dict to the correct typed subclass based on the type field."""
    t = data.get("noun", {}).get("type", "")
    if t == NounType.CHARACTER.value or t == "character":
        return Character.from_response(data)
    elif t == NounType.FACTION.value or t == "faction":
        return Faction.from_response(data)
    elif t == NounType.LOCATION.value or t == "location":
        return Location.from_response(data)
    elif t == NounType.ITEM.value or t == "item":
        return Item.from_response(data)
    else:
        raise ValueError(f"Unknown noun type: {t!r}")


class Noun_Controller():
    def __init__(self):
        self.noun_repository: Noun_Repository = Noun_Repository()

    def assign_agents(self, GeneratorAgent: Agent, RetrieverAgent: Agent, UpdateFlagAgent: Agent):
        self.generator_agent = GeneratorAgent
        self.retriever_agent = RetrieverAgent
        self.update_flag_agent = UpdateFlagAgent

    def to_dict(self):
        return {
            "noun_repository": self.noun_repository.to_dict()
        }
    
    @staticmethod
    def from_dict(data: dict):
        controller = Noun_Controller()
        controller.noun_repository = Noun_Repository.from_dict(data.get("noun_repository", {}))
        return controller

    async def seed_from_story_template(self, story_template_directory: str):
        # Look for config story.json file (Other files are loaded by the system prompt compiler not here)
        print(f"[SEEDING] Seeding start...")
        if os.path.exists(f"{story_template_directory}/story.json"):
            print(f"[SEEDING] Found story.json, seeding initial nouns from config file...")
            with open(f"{story_template_directory}/story.json", "r") as f:
                config_file = json.load(f)
            nouns = config_file.get("nouns", {})
            initial_factions = nouns.get("initial_factions", [])
            initial_characters = nouns.get("initial_characters", [])
            initial_locations = nouns.get("initial_locations", [])
            initial_items = nouns.get("initial_items", [])
            all_initial_nouns = initial_factions + initial_characters + initial_locations + initial_items
            for noun_data in all_initial_nouns:
                self.noun_repository[noun_data["name"]] = _noun_from_data(noun_data)
        else:
            print(f"[SEEDING] No story.json found, skipping config-based seeding.")

        world_def = None
        if os.path.exists(f"{story_template_directory}/World Definition.md"):
            print(f"[SEEDING] Found World Definition.md, seeding initial nouns from world definition...")
            with open(f"{story_template_directory}/World Definition.md", "r", encoding='utf-8') as md_file:
                world_def = md_file.read()
        else:
            print(f"[SEEDING] No World Definition.md found, skipping world definition-based seeding.")

        if world_def is not None:
            response: str = await self.generator_agent.generate_text_in_background(
                f'[SEEDING NOUN REPOSITORY WITH INITIAL WORLD DEFINITION]\n'
                f"## World Definition\n{world_def}\n",
                temperature=0.4,
            )
            try:
                parsed_response = json.loads(response)
                for noun_data in parsed_response:
                    noun = _noun_from_data(noun_data)
                    print(f"[SEEDING] Adding noun from world definition: {noun.noun.name}")
                    self.noun_repository[noun.noun.name] = noun
            except json.JSONDecodeError as e:
                print(f"[SEEDING] Error decoding JSON from world definition retrieval: {e}")

        
        player_def = None
        if os.path.exists(f"{story_template_directory}/Player Character.md"):
            with open(f"{story_template_directory}/Player Character.md", "r", encoding='utf-8') as md_file:
                player_def = md_file.read()

        if player_def is not None:
            response: str = await self.generator_agent.generate_text_in_background(
                f'[SEEDING NOUN REPOSITORY WITH INITIAL PLAYER CHARACTER DEFINITION]\n'
                f"## Player Character Definition\n{player_def}\n",
                temperature=0.4,
            )
            try:
                parsed_response = json.loads(response)
                for noun_data in parsed_response:
                    noun = _noun_from_data(noun_data)
                    print(f"[SEEDING] Adding player character noun: {noun.noun.name}")
                    self.noun_repository[noun.noun.name] = noun
            except json.JSONDecodeError as e:
                print(f"[SEEDING] Error decoding JSON from player character definition retrieval: {e}")

        nouns_def = None
        if os.path.exists(f"{story_template_directory}/Nouns.md"):
            with open(f"{story_template_directory}/Nouns.md", "r", encoding='utf-8') as md_file:
                nouns_def = md_file.read()
                
        if nouns_def is not None:
            response: str = await self.generator_agent.generate_text_in_background(
                f'[SEEDING NOUN REPOSITORY WITH INITIAL NOUNS DEFINED IN NOUNS.md]\n'
                f"## Nouns Definition\n{nouns_def}\n",
                temperature=0.4,
            )
            try:
                parsed_response = json.loads(response)
                for noun_data in parsed_response:
                    noun = _noun_from_data(noun_data)
                    print(f"[SEEDING] Adding noun from Nouns.md: {noun.noun.name}")
                    self.noun_repository[noun.noun.name] = noun
            except json.JSONDecodeError as e:
                print(f"[SEEDING] Error decoding JSON from nouns definition retrieval: {e}")

    def get_short_list(self):
        factions = [self.noun_repository.factions[key].noun.to_dict() for key in self.noun_repository.factions]
        characters = [self.noun_repository.characters[key].noun.to_dict() for key in self.noun_repository.characters]
        locations = [self.noun_repository.locations[key].noun.to_dict() for key in self.noun_repository.locations]
        items = [self.noun_repository.items[key].noun.to_dict() for key in self.noun_repository.items]
        return {
            "factions": factions,
            "characters": characters,
            "locations": locations,
            "items": items
        }
    
    async def get_injected_nouns(self, last_turn: str, current_plan: str):
        
        relevant_nouns = await self.__retrieve_relative_nouns(last_turn, current_plan)

        query_miss = []
        nouns = []
        for noun_name in relevant_nouns:
            query_result = self.noun_repository.get(noun_name)
            if query_result is None:
                query_miss.append(noun_name)
            else:
                nouns.append(query_result)

        return nouns, query_miss

    async def update_nouns(self, last_turn: str):
        updates = await self.__poll_for_noun_updates(last_turn)

        if updates == []:
            return None
        
        for update in updates:
            try:
                update_dict = update if isinstance(update, dict) else json.loads(update)
            except (json.JSONDecodeError, TypeError):
                print(f"Invalid JSON update received: {update}")
                continue

            update = NounDiff.from_response(update_dict)
            noun = self.noun_repository.get(update.name)

            response: str = await self.__generate_update(update, noun, last_turn)
            if update.action == "delete" and response == "confirm":
                self.noun_repository.delete_noun(update.name)

            if update.action in ["create", "update"] and response != "confirm":
                try:
                    json_response = json.loads(response)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for noun '{update.name}': {e}")
                    continue

                new_noun = None
                if update.type == NounType.CHARACTER:
                    new_noun = Character.from_response(json_response)
                elif update.type == NounType.FACTION:
                    new_noun = Faction.from_response(json_response)
                elif update.type == NounType.LOCATION:
                    new_noun = Location.from_response(json_response)
                elif update.type == NounType.ITEM:
                    new_noun = Item.from_response(json_response)

                if isinstance(new_noun, str): # If the response was an error message instead of a noun object
                    print(f"Error updating noun '{update.name}': {new_noun}")
                else:
                    self.noun_repository[update.name] = new_noun
        
    async def __generate_update(self, update: 'NounDiff', noun, last_turn: str):
        noun_data = json.dumps(noun.to_dict()) if noun is not None else "None — this is a new entry"
        response: str = await self.generator_agent.generate_text_in_background(
            f"## Current Noun Data\n{noun_data}\n"
            f"---\n"
            f"## Update Type\n{update.action}\n"
            f"---\n"
            f"## Changes\n{update.changes}\n"
            f"---\n"
            f"## Last Turn\n{last_turn}\n",
            temperature=0.4,
        )
        return response
        

    async def __poll_for_noun_updates(self, last_turn: str):
        response: str = await self.update_flag_agent.generate_text_in_background(
            f"## Full Index\n{json.dumps(self.get_short_list())}\n"
            f"---\n"
            f"## Last Turn\n{last_turn}\n",
            temperature=0.4,
        )
        try:
            parsed_response = json.loads(response)
            if not isinstance(parsed_response, list):
                parsed_response = [parsed_response]
            return parsed_response
        except json.JSONDecodeError as e:
            print(f"Error parsing update flag response: {e}")
            return []
        

    async def __retrieve_relative_nouns(self, last_turn: str, current_plan: str) -> list:
        response: str = await self.retriever_agent.generate_text_in_background(
            f"## Full Index\n{json.dumps(self.get_short_list())}\n"
            f"---\n"
            f"## Planner Notes:\n{current_plan}\n"
            f"---\n"
            f'## Last Turn\n{last_turn}\n',
            temperature=0.4,
        )
        try:
            parsed_response = json.loads(response)
            if not isinstance(parsed_response, list):
                parsed_response = [parsed_response]
            return parsed_response
        except json.JSONDecodeError as e:
            print(f"Error parsing retriever response: {e}")
            return []

class Noun():
    def __init__(self, name: str, noun_type: NounType, keywords: list[str] = None, always_show: bool = False, summary: str = ""):
        self.name = name
        self.type = noun_type
        self.keywords = keywords if keywords is not None else []
        self.always_show = always_show
        self.summary = summary

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type.value,
            "keywords": self.keywords,
            "always_show": self.always_show,
            "summary": self.summary
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Noun(
                name= data["name"],
                noun_type= NounType(data["type"]),
                keywords= data["keywords"],
                always_show= data["always_show"],
                summary= data["summary"]
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid noun data: {e}")    
    

class Character_static_data:
    def __init__(self, appearance: str = "", background: str = "", personality: str = "", relationship_to_player: str = ""):
        self.appearance = appearance
        self.background = background
        self.personality = personality
        self.relationship_to_player = relationship_to_player

    def to_dict(self):
        return {
            "appearance": self.appearance,
            "background": self.background,
            "personality": self.personality,
            "relationship_to_player": self.relationship_to_player
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Character_static_data(
                appearance= data["appearance"],
                background= data["background"],
                personality= data["personality"],
                relationship_to_player= data["relationship_to_player"]
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid character static data: {e}")


class Character_dynamic_data:
    def __init__(self, last_seen: str = "", current_mood: str = "", current_location: str = "", last_action: str = ""):
        self.last_seen = last_seen
        self.current_mood = current_mood
        self.current_location = current_location
        self.last_action = last_action

    def to_dict(self):
        return {
            "last_seen": self.last_seen,
            "current_mood": self.current_mood,
            "current_location": self.current_location,
            "last_action": self.last_action
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Character_dynamic_data(
                last_seen= data["last_seen"],
                current_mood= data["current_mood"],
                current_location= data["current_location"],
                last_action= data["last_action"]
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid character dynamic data: {e}")


class Character:
    def __init__(self, noun: Noun, static_data: Character_static_data, dynamic_data: Character_dynamic_data):
        self.noun = noun
        self.static_data = static_data
        self.dynamic_data = dynamic_data

    def to_dict(self):
        return {
            "noun": self.noun.to_dict(),
            "static_data": self.static_data.to_dict(),
            "dynamic_data": self.dynamic_data.to_dict()
        }
    
    @staticmethod
    def from_response(response_json: str) -> Union['Character', str]:
        try:
            noun = Noun.from_response(response_json["noun"])
            static_data = Character_static_data.from_response(response_json["static_data"])
            dynamic_data = Character_dynamic_data.from_response(response_json["dynamic_data"])
            return Character(noun, static_data, dynamic_data)
        except (ValueError, KeyError) as e:
            return str(e)
    

class Location:
    def __init__(self, noun: Noun, style: str = "", access: str = "", rooms: list[dict] = None, notes: str = ""):
        self.noun = noun
        self.style = style
        self.access = access
        self.rooms = rooms if rooms is not None else []
        self.notes = notes

    def to_dict(self):
        return {
            "noun": self.noun.to_dict(),
            "style": self.style,
            "access": self.access,
            "rooms": self.rooms,
            "notes": self.notes
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Location(
                noun=Noun.from_response(data["noun"]),
                style=data["style"],
                access=data["access"],
                rooms=data["rooms"],
                notes=data["notes"]
            )
        except (ValueError, KeyError) as e:
            return str(e)


class Faction:
    def __init__(self, noun: Noun, members: list[str] = None, rules: str = "", motivations: str = "", style: str = "", relationship_to_player: str = ""):
        self.noun = noun
        self.members = members if members is not None else []
        self.rules = rules
        self.motivations = motivations
        self.style = style
        self.relationship_to_player = relationship_to_player

    def to_dict(self):
        return {
            "noun": self.noun.to_dict(),
            "members": self.members,
            "rules": self.rules,
            "motivations": self.motivations,
            "style": self.style,
            "relationship_to_player": self.relationship_to_player
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Faction(
                noun=Noun.from_response(data["noun"]),
                members=data["members"],
                rules=data["rules"],
                motivations=data["motivations"],
                style=data["style"],
                relationship_to_player=data["relationship_to_player"]
            )
        except (ValueError, KeyError) as e:
            return str(e)


class Item:
    def __init__(self, noun: Noun, description: str = "", significance: str = "", current_holder: str = "", notes: str = ""):
        self.noun = noun
        self.description = description
        self.significance = significance
        self.current_holder = current_holder
        self.notes = notes

    def to_dict(self):
        return {
            "noun": self.noun.to_dict(),
            "description": self.description,
            "significance": self.significance,
            "current_holder": self.current_holder,
            "notes": self.notes
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return Item(
                noun=Noun.from_response(data["noun"]),
                description=data["description"],
                significance=data["significance"],
                current_holder=data["current_holder"],
                notes=data["notes"]
            )
        except (ValueError, KeyError) as e:
            return str(e)
        

class NounDiff():
    def __init__(self, action: str, name: str, type: NounType, changes: str):
        self.action = action
        self.name = name
        self.type = type
        self.changes = changes

    def to_dict(self):
        return {
            "action": self.action,
            "name": self.name,
            "type": self.type.value,
            "changes": self.changes
        }
    
    @staticmethod
    def from_response(data: dict):
        try:
            return NounDiff(
                action=data["action"],
                name=data["name"],
                type=NounType(data["type"]),
                changes=data["changes"]
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid noun diff data: {e}")