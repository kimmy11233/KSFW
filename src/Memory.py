class Memory:
    def __init__(self):
        self.events: list[str] = []
        self.rules: str = ""        
        self.current_state: str = ""   

    def to_dict(self):
        return {
            "events": self.events,
            "rules": self.rules,
            "current_state": self.current_state,
        }

    def from_dict(self, data: dict):
        self.events         = data.get("events", [])
        self.rules          = data.get("rules", "")
        self.current_state  = data.get("current_state", "")

    def overwrite_events(self, new_events_blob: list[str]):
        self.events = new_events_blob

    def overwrite_rules(self, new_rules_blob: str):
        self.rules = new_rules_blob.strip()

    def get_memory_summary(self) -> str:
        """
        Assembles the full memory block for injection into agent prompts.
        Sections with no content are omitted.
        """
        parts = []

        if self.current_state:
            parts.append(self.current_state)

        if self.rules:
            parts.append(self.rules)

        if self.events:
            parts.append("[EVENTS]")
            for event in self.events:
                parts.append(f"- {event}")

        return "\n".join(parts)