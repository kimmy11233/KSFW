# !/usr/bin/env python3
from src.Roleplay import Roleplay
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import webbrowser, threading
import logging
import uvicorn
import os
from dotenv import load_dotenv
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
            "turn_number": 0
        }
    return {
        "title": ROLEPLAY_SYSTEM.STORY.title,
        "messages": [m.to_dict() for m in ROLEPLAY_SYSTEM.STORY.messages],
        "memory": ROLEPLAY_SYSTEM.STORY.memory,
        "inventory": ROLEPLAY_SYSTEM.STORY.inventory,
        "turn_number": ROLEPLAY_SYSTEM.STORY.turn_number
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
    ROLEPLAY_SYSTEM.STORY.save(ROLEPLAY_SYSTEM.load_path)
    return JSONResponse({"status": "success", "new_inventory": ROLEPLAY_SYSTEM.STORY.inventory})


@app.post("/api/overwrite_memory")
async def overwrite_memory(req: Request):
    data = await req.json()
    new_memory = data.get("memory", "")
    assert ROLEPLAY_SYSTEM is not None
    ROLEPLAY_SYSTEM.STORY.memory = new_memory
    ROLEPLAY_SYSTEM.STORY.save(ROLEPLAY_SYSTEM.load_path)
    return JSONResponse({"status": "success", "new_memory": ROLEPLAY_SYSTEM.STORY.memory})

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
        ROLEPLAY_SYSTEM = Roleplay(SELECTED_STORY_DIRECTORY, SAVED_STORIES_DIRECTORY, path)
        return JSONResponse({"status": "success", "loaded": filename})
    except Exception as e:
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
        ROLEPLAY_SYSTEM = Roleplay(template_path, SAVED_STORIES_DIRECTORY, None)
        return JSONResponse({"status": "success", "template": template})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8080/home")).start()
    uvicorn.run("Main:app", host="127.0.0.1", port=8080, reload=True)