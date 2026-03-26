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

### Installation

1. rename .env.dist to .env and add your API key
2. ./setup.bat
3. ./launch.bat
- If you ever need to get back to the webpage and don't want to start it tries to open at http://localhost:8080/home

### Adding or sharing
The easiest way to share stories is by zipping the template directory. The reverse is just unzipping the story in `./Story Templates`

### Making your own story a story
A story is composed of a few files. The files are
| File | Purpose | Format | Description | Optional |
|------|---------|--------|-------------|----------|
| `World Definition.md` | World settings | Markdown | Defines the world, environment, and lore | No |
| `Player Character.md` | Character details | Markdown | Player character stats, background, and traits | No |
| `story.json` | Story configuration | JSON | Story metadata like name. You can also fully define Nouns here in proper syntax | No |
| `Nouns.md` | Noun definitions | Markdown | Factions, characters, locations, and items in plain text | No |

You can look at other examples of world definitions to get ideas. Realistically it should cover the tone of your world, the basic structure, how it starts, anything that you want to happen. It can be fairly plane text markdown, but I highly recommend using an LLM as they are more verbose and can expand ideas for you.

`Player Character.md` is all about you, try to be verbose. It will be seeded for you by an LLM into a noun. Currently it is also shown to the main writer to try to ensure it keeps its focus on you.

`story.json` — Settings for the story and metadata needs to be filled out. Its not the biggiest issue. You can also write nouns here which will be directly seeded, not fed through an LLM like the others routs. For the inventory you can write things you want to start with or just write [STORY START] 

For detailed noun structures, see the [Nouns](#nouns) section below.

`Nouns.md` any other factions, significant characters, or locations can be described in plane text here. 

Where do I put nouns?
    They can be put in any of the files or directly defined in Story.json. However there are impacts to putting them into the world definition. My recommendation is you in Player Character.md, none any World Definition.md, factions, other characters, items, locations in Nouns.md. The main thing is don't define them in two places. This system will be cleaned up eventually.

You can copy the template `__blank__` or start from any other story you have.


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

## Nouns
Part of the system memory is about remembering and managing Proper Nouns or "Nouns" for short. This is any faction, character, location, or significant item. The system polls for what items need to be shown to the author. You can always set `always_show` to true if you want to make sure its always included.

### Character Entry

```json
{
  "name": "",
  "type": "character",
  "keywords": [],
  "always_show": false,
  "summary": "",
  "static": {
    "appearance": "",
    "background": "",
    "personality": "",
    "relationship_to_player": ""
  },
  "dynamic": {
    "last_seen": "",
    "current_mood": "",
    "current_location": "",
    "last_action": ""
  }
}
```

Static fields are set at creation and should rarely change. Dynamic fields are updated each turn by the update agent.

---

### Location Entry

```json
{
  "name": "",
  "type": "location",
  "keywords": [],
  "always_show": false,
  "summary": "",
  "style": "",
  "access": "",
  "rooms": [
    {
      "name": "",
      "description": "",
      "contents": ""
    }
  ],
  "notes": ""
}
```

The `access` field records who can enter, what is locked, and what requires a key. This is where location-level access control lives (not in arrangements).

---

### Faction Entry

```json
{
  "name": "",
  "type": "faction",
  "keywords": [],
  "always_show": false,
  "summary": "",
  "members": [],
  "rules": "",
  "motivations": "",
  "style": "",
  "relationship_to_player": ""
}
```

---

### Item Entry

```json
{
  "name": "",
  "type": "item",
  "keywords": [],
  "always_show": false,
  "summary": "",
  "description": "",
  "significance": "",
  "current_holder": "",
  "notes": ""
}
```
