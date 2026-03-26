# !/usr/bin/env python3
from src.Roleplay import Roleplay
from src.Nouns import _noun_from_data
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import traceback

import webbrowser, threading
import logging
import uvicorn
import os
from dotenv import load_dotenv

from src.Story import Story
load_dotenv()

IMAGE_PATH = "./tmp/output.png" if os.path.exists("./tmp/output.png") else ""

SELECTED_STORY_DIRECTORY = "./Story Templates/MOB"
LOAD_PATH = None
SAVED_STORIES_DIRECTORY = "./saves"
TEMPLATES_DIRECTORY = "./Story Templates"

ROLEPLAY_SYSTEM: Roleplay | None = None


# Ensure log directory exists
os.makedirs("./logs/api", exist_ok=True)

app = FastAPI()
logging.getLogger("uvicorn.access").disabled = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/home", StaticFiles(directory=frontend_path, html=True), name="frontend")

@app.get("/api/messages")
def get_messages():
    if ROLEPLAY_SYSTEM is None:
        return {
            "title": "No Story Loaded",
            "messages": [],
            "memory": "",
            "inventory": "",
            "turn_number": 0,
            "time_estimate": ""
        }
    return {
        "title": ROLEPLAY_SYSTEM.STORY.title,
        "messages": [m.to_dict() for m in ROLEPLAY_SYSTEM.STORY.messages],
        "memory": ROLEPLAY_SYSTEM.STORY.memory,
        "inventory": ROLEPLAY_SYSTEM.STORY.inventory,
        "turn_number": ROLEPLAY_SYSTEM.STORY.turn_number,
        "time_estimate": ROLEPLAY_SYSTEM.STORY.last_time_est 
    }


@app.get("/api/agents")
def get_agents():
    if ROLEPLAY_SYSTEM is None:
        return {"agents": []}
    return [agent.to_dict() for agent in ROLEPLAY_SYSTEM.AGENTS.values()]


@app.get("/api/image")
def get_image():
    path = IMAGE_PATH if IMAGE_PATH else "./tmp/output.png"
    if os.path.exists(path):
        return {"image_url": f"/api/static_image?ts={int(os.path.getmtime(path))}"}
    return {"image_url": ""}


@app.get("/api/static_image")
def static_image():
    path = IMAGE_PATH if IMAGE_PATH else "./tmp/output.png"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse({}, status_code=404)


@app.post("/api/prompt")
async def submit_prompt(req: Request):
    data = await req.json()
    prompt = data.get("prompt", "")
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    async def event_stream():
        assert ROLEPLAY_SYSTEM is not None
        async for chunk in ROLEPLAY_SYSTEM.stream_response(prompt):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain")


@app.post("/api/overwrite_inventory")
async def overwrite_inventory(req: Request):
    data = await req.json()
    new_inventory = data.get("inventory", "")
    assert ROLEPLAY_SYSTEM is not None
    ROLEPLAY_SYSTEM.STORY.inventory = new_inventory
    ROLEPLAY_SYSTEM.STORY.save()
    return JSONResponse({"status": "success", "new_inventory": ROLEPLAY_SYSTEM.STORY.inventory})


@app.post("/api/overwrite_memory")
async def overwrite_memory(req: Request):
    assert ROLEPLAY_SYSTEM is not None

    data = await req.json()
    memory_sector = data.get("memory_sector", "")
    memory_sector = 'characters' if memory_sector == "characters_raw" else memory_sector
    if memory_sector not in ["events", "facts", "rules", "characters"]:
        return JSONResponse({"error": "Invalid memory sector"}, status_code=400)

    new_memory = data.get("memory", "")
    if memory_sector == "events":
        if type(new_memory) is not list:
            return JSONResponse({"error": "Events memory must be a list of strings"}, status_code=400)
        ROLEPLAY_SYSTEM.STORY.memory.overwrite_events(new_memory)
    elif memory_sector == "facts":
        if type(new_memory) is not list:
            return JSONResponse({"error": "Facts memory must be a list of strings"}, status_code=400)

        ROLEPLAY_SYSTEM.STORY.memory.overwrite_facts(new_memory)
    elif memory_sector == "rules":
        ROLEPLAY_SYSTEM.STORY.memory.overwrite_rules(new_memory)
    elif memory_sector == "characters":
        ROLEPLAY_SYSTEM.STORY.memory.overwrite_characters(new_memory)
    ROLEPLAY_SYSTEM.STORY.save()
    return JSONResponse({"status": "success", "new_memory": ROLEPLAY_SYSTEM.STORY.memory.to_dict()})


@app.get("/api/get_nouns")
def get_nouns():
    if ROLEPLAY_SYSTEM is None:
        return {"nouns": []}
    return {
        "characters": [char.to_dict() for char in ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.characters.values()],
        "factions": [faction.to_dict() for faction in ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.factions.values()],
        "locations": [location.to_dict() for location in ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.locations.values()],
        "items": [item.to_dict() for item in ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.items.values()],
    }

@app.post("/api/overwrite_noun")
async def overwrite_noun_endpoint(req: Request):
    data = await req.json()
    try:
        noun = _noun_from_data(data)

        if noun.noun.type not in ["character", "faction", "location", "item"]:
            return JSONResponse({"error": "Invalid noun type"}, status_code=400)
        if ROLEPLAY_SYSTEM is None:
            return JSONResponse({"error": "No story loaded"}, status_code=400)
        
        if noun.noun.type == "character":
            ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.characters[noun.noun.name] = noun
        elif noun.noun.type == "faction":
            ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.factions[noun.noun.name] = noun
        elif noun.noun.type == "location":
            ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.locations[noun.noun.name] = noun
        elif noun.noun.type == "item":
            ROLEPLAY_SYSTEM.STORY.nouns_controller.noun_repository.items[noun.noun.name] = noun
        return JSONResponse({"status": "success"})
    
    except ValueError as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=400)



@app.get("/api/get_saved_stories")
def get_saved_stories():
    os.makedirs(SAVED_STORIES_DIRECTORY, exist_ok=True)
    try:
        files = [
            f for f in os.listdir(SAVED_STORIES_DIRECTORY)
            if f.endswith(".json")
        ]
        files.sort(key=lambda f: os.path.getmtime(
            os.path.join(SAVED_STORIES_DIRECTORY, f)), reverse=True)
        return {"stories": files}
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/load_story")
async def load_story(req: Request):
    global ROLEPLAY_SYSTEM
    data = await req.json()
    filename = data.get("filename", "")

    if not filename:
        return JSONResponse({"error": "No filename provided"}, status_code=400)
    path = os.path.join(SAVED_STORIES_DIRECTORY, filename)

    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    
    try:      
        ROLEPLAY_SYSTEM = Roleplay(Story.load(path)) # Load the story from the selected file and create a new roleplay system with it
        return JSONResponse({"status": "success", "loaded": filename})
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/get_templates")
def get_templates():
    try:
        templates = [
            d for d in os.listdir(TEMPLATES_DIRECTORY)
            if os.path.isdir(os.path.join(TEMPLATES_DIRECTORY, d))
        ]
        templates.sort()
        return {"templates": templates}
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/get_agent_last_response")
async def get_agent_last_response(agent_id: str):
    if ROLEPLAY_SYSTEM is None:
        return JSONResponse({"error": "No story loaded"}, status_code=400)

    agent = ROLEPLAY_SYSTEM.AGENTS.get(agent_id)
    if agent is None:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    if not hasattr(agent, "last_response_file_path") or agent.last_response_file_path is None:
        return JSONResponse({"error": "No last response available"}, status_code=404)

    try:
        if not os.path.exists(agent.last_response_file_path):
            return JSONResponse({"error": "Last response file not found"}, status_code=404)
        with open(agent.last_response_file_path, 'r', encoding='utf-8') as f:
            last_response = f.read()
        return JSONResponse({"last_response": last_response})
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/create_from_template")
async def create_from_template(req: Request):
    global ROLEPLAY_SYSTEM
    data = await req.json()
    template = data.get("template", "")

    if not template:
        return JSONResponse({"error": "No template provided"}, status_code=400)
    template_path = os.path.join(TEMPLATES_DIRECTORY, template)

    if not os.path.isdir(template_path):
        return JSONResponse({"error": "Template not found"}, status_code=404)
    
    try:
        ROLEPLAY_SYSTEM = Roleplay(Story(template_path, SAVED_STORIES_DIRECTORY)) # Create a story from just a template
        await ROLEPLAY_SYSTEM.seed_story() # Seed the story's noun controller with the template data
        return JSONResponse({"status": "success", "template": template})
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.post("/api/restore_from_backup")
async def restore_from_backup(req: Request):
    global ROLEPLAY_SYSTEM
    if ROLEPLAY_SYSTEM is None:
        return JSONResponse({"error": "No story loaded"}, status_code=400)

    try:
        restored_story = ROLEPLAY_SYSTEM.STORY.restore_from_backup()
        if restored_story is None:
            return JSONResponse({"error": "No backups found"}, status_code=404)
        ROLEPLAY_SYSTEM = Roleplay(restored_story) # Create a new roleplay system with the restored story
        return JSONResponse({"status": "success"})
    
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8080/home")).start()
    uvicorn.run("Main:app", host="127.0.0.1", port=8080, reload=True)