# Kimmy's Statistically Finite Worlds


## Project Structure

- `Main.py` — FastAPI server, API endpoints, and static file serving.
- `frontend/` — Web UI (HTML, JS, CSS).
- `src/` — Core logic: agents, connectors, story management.
- `Story Templates/` — Story template folders (with agent/system prompts and config).
- `saves/` — Saved story states.
- `tmp/` — If you are curious what an agent is doing you can look here to see their last prompt and output.
- `logs/` — API and system logs.

## Getting Started

### Prerequisites

- Python 3.8+
- A deepseek API key. https://api-docs.deepseek.com/
    - I have spend 88 cents so far with all the testing ive done, so 5 bucks is a fair amount to load to it

### Installation

1. rename .env.dist to .env and add your API key
2. ./setup.bat
3. ./launch.bat
- If you ever need to get back to the webpage and don't want to start it tries to open at http://localhost:8080/home

### Adding a story
You are likely either adding one of my stories or writing your own. I will separately provide a blank template.
You can edit anything you like but the world description and the player description and story are the key ones here. If starting from the template
make sure you fill them both out, if starting from mine just fill out the player and try not to peek at the world. It will spoil things!
The easiest way to make a story is provide a World description from my world and then give it claud and describe the new world you want and have it rewrite it. Then ask it for a first message and put that into storage.

To be clear:
Player Description: Needs to be edited
World Description: Needs to be edited if you are starting from blank
Story.json: Needs to be edited if you are starting from blank
Everything else is edit at your own risk

### Known bugs
* Edits sometimes butcher whitespace. We love vibe code jank!
* Edits sometimes be editing when they dont need editing. Because this is still in the work sometimes a violation is fired when the actual
story is fine, the agent is just a little happy to set it on fire, its annoying but harmless. I hope to kill it, testing will help.

### Usage
- Access the web UI to start a new story or load a saved one.
- Add or modify story templates in `Story Templates/`

## API Endpoints
- `/docs` — API docs.
- `/api/messages` — Get current story messages.
- `/api/agents` — List active agents.
- `/api/prompt` — Submit a prompt to the story.
- `/api/overwrite_inventory` — Update inventory.
- `/api/overwrite_memory` — Update memory.
- `/api/get_saved_stories` — List saved stories.
- `/api/load_story` — Load a saved story.
- `/api/get_templates` — List available templates.
- `/api/create_from_template` — Start a new story from a template.
- `/api/image` — Get current story image.
