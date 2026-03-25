class Memory:
    def __init__(self):
        self.events: list[str] = []
        self.characters_raw: str = ""   # full [CHARACTERS] block as returned by the agent
        self.facts: list[str] = []
        self.rules: str = ""            # full [RULES & ROUTINES] block
        self.current_state: str = ""    # full [CURRENT STATE] block

    def to_dict(self):
        return {
            "events": self.events,
            "characters_raw": self.characters_raw,
            "facts": self.facts,
            "rules": self.rules,
            "current_state": self.current_state,
        }

    def from_dict(self, data: dict):
        self.events         = data.get("events", [])
        self.facts          = data.get("facts", [])
        self.rules          = data.get("rules", "")
        self.current_state  = data.get("current_state", "")

        # Support both old key ("characters") and new key ("characters_raw")
        # so existing saves load cleanly
        self.characters_raw = (
            data.get("characters_raw")
            or "\n".join(data.get("characters", []))
            or ""
        )

    def get_memory_summary(self) -> str:
        """
        Assembles the full memory block for injection into agent prompts.
        Sections with no content are omitted.
        """
        parts = []

        if self.current_state:
            parts.append(self.current_state)

        if self.characters_raw:
            parts.append(self.characters_raw)

        if self.rules:
            parts.append(self.rules)

        if self.facts:
            parts.append("[FACTS]")
            for fact in self.facts:
                parts.append(f"- {fact}")

        if self.events:
            parts.append("[EVENTS]")
            for event in self.events:
                parts.append(f"- {event}")

        return "\n".join(parts)