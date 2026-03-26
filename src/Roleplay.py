from src.Agent import ImageAgent, TextAgent, AgentStatus
from src.OpenRouterAPIConnector import OpenRouterAPIConnector
from src.SDUIConnector import SDUIConnector
from src.SystemPromptCompiler import SystemPromptCompiler
from src.DeepSeekConnector import DeepSeekAPIConnector
from src.Story import Message, Story

import asyncio
import difflib
import json
import os
import re
import traceback
import datetime


# ── Agent IDs ─────────────────────────────────────────────────────────────────
WRITER_ID                  = "writer_agent"
PLANNER_ID                 = "planner_agent"
CHECKER_RESTRAINT_ID       = "checker_restraint"
CHECKER_WORLD_ID           = "checker_world"
CHECKER_CHARACTER_ID       = "checker_character"
CHECKER_MEMORY_ID          = "checker_memory"
FIXER_ID                   = "fixer_agent"
INVENTORY_ID               = "inventory_agent"
TIME_ID                    = "time_estimation_agent"
MEMORY_FACTS_ID            = "memory_facts_agent"
MEMORY_EVENTS_ID           = "memory_events_agent"
MEMORY_CHARACTER_ID        = "memory_character_agent"
MEMORY_CURRENT_STATE_ID    = "memory_current_state_agent"
MEMORY_RULES_ID            = "memory_rules_agent"
STOP_POINT_AGENT           = "stop_point_agent"


async def _ensure(task: asyncio.Task):
    """Await a task silently — used to let fire-and-forget tasks complete
    without blocking the caller if they haven't finished yet."""
    try:
        await task
    except Exception as e:
        print(f"Error in {_ensure.__name__}: {e}")


class Roleplay():
    def __init__(self, story: Story):

        self.STORY: Story = story
        self.COMPRESSION_TURN = self.STORY.config.get("compression_turn", 20)
        self.IMAGE_GENERATION_ENABLED = False

        # ── Connectors ────────────────────────────────────────────────────────

        openrouter_api_key: str | None = os.getenv('OPENROUTER_API_KEY')
        deepseek_api_key: str | None = os.getenv('DEEPSEEK_API_KEY')
        if openrouter_api_key and deepseek_api_key:
            raise ValueError('Both OPENROUTER_API_KEY and DEEPSEEK_API_KEY defined, please chose oneeeeeee!!!')
        elif openrouter_api_key:
            deep = OpenRouterAPIConnector(openrouter_api_key)
        elif deepseek_api_key:
            deep = DeepSeekAPIConnector(deepseek_api_key)
        else:
            raise ValueError('Please define DEEPSEEK_API_KEY in the .env file')

        # ── Agents ────────────────────────────────────────────────────────────
        writer_agent                = TextAgent(WRITER_ID,            "Writer Agent",           "", deep)
        planner_agent               = TextAgent(PLANNER_ID,           "Planner Agent",          "", deep)
        checker_restraint_agent     = TextAgent(CHECKER_RESTRAINT_ID, "Restraint Checker",      "", deep)
        checker_world_agent         = TextAgent(CHECKER_WORLD_ID,     "World Checker",          "", deep)
        checker_character_agent     = TextAgent(CHECKER_CHARACTER_ID, "Character Checker",      "", deep)
        checker_memory_agent        = TextAgent(CHECKER_MEMORY_ID,    "Memory Checker",         "", deep)
        fixer_agent                 = TextAgent(FIXER_ID,             "Fixer Agent",            "", deep)
        inventory_agent             = TextAgent(INVENTORY_ID,         "Inventory Agent",        "", deep)
        time_estimation_agent       = TextAgent(TIME_ID,              "Time Estimation Agent",  "", deep)
        memory_facts_agent          = TextAgent(MEMORY_FACTS_ID,      "Facts Agent",            "", deep)
        memory_events_agent         = TextAgent(MEMORY_EVENTS_ID,     "Events Agent",           "", deep)
        memory_character_agent      = TextAgent(MEMORY_CHARACTER_ID,  "Character Agent",        "", deep)
        memory_current_state_agent  = TextAgent(MEMORY_CURRENT_STATE_ID, "Current State Agent", "", deep)
        memory_rules_agent          = TextAgent(MEMORY_RULES_ID,      "Rules Agent",            "", deep)
        stop_point_agent           = TextAgent(STOP_POINT_AGENT,     "Stop Point Agent",        "", deep)

        self.AGENTS = {
            WRITER_ID:            writer_agent,
            CHECKER_RESTRAINT_ID: checker_restraint_agent,
            CHECKER_WORLD_ID:     checker_world_agent,
            CHECKER_CHARACTER_ID: checker_character_agent,
            CHECKER_MEMORY_ID:    checker_memory_agent,
            INVENTORY_ID:         inventory_agent,
            TIME_ID:              time_estimation_agent,
            PLANNER_ID:           planner_agent,
            FIXER_ID:             fixer_agent,
            MEMORY_FACTS_ID:      memory_facts_agent,
            MEMORY_EVENTS_ID:     memory_events_agent,
            MEMORY_CHARACTER_ID:  memory_character_agent,
            MEMORY_CURRENT_STATE_ID: memory_current_state_agent,
            MEMORY_RULES_ID:      memory_rules_agent,
            STOP_POINT_AGENT:     stop_point_agent,
        }

        # ── System prompt compilation ──────────────────────────────────────────
        compiler = SystemPromptCompiler()
        compiler.import_system_prompt(self.STORY.story_template_path)
        compiler.compile_system_prompt(writer_agent,               "Writer Agent")
        compiler.compile_system_prompt(planner_agent,              "Planner Agent")
        compiler.compile_system_prompt(checker_restraint_agent,    "Restraint Checker")
        compiler.compile_system_prompt(checker_world_agent,        "World Checker")
        compiler.compile_system_prompt(checker_character_agent,    "Character Checker")
        compiler.compile_system_prompt(checker_memory_agent,       "Memory Checker")
        compiler.compile_system_prompt(fixer_agent,                "Fixer Agent")
        compiler.compile_system_prompt(inventory_agent,            "Inventory Manager")
        compiler.compile_system_prompt(time_estimation_agent,      "Time Estimator")
        compiler.compile_system_prompt(memory_facts_agent,         "Facts Agent")
        compiler.compile_system_prompt(memory_events_agent,        "Events Agent")
        compiler.compile_system_prompt(memory_character_agent,     "Character Agent")
        compiler.compile_system_prompt(memory_current_state_agent, "Current State Agent")
        compiler.compile_system_prompt(memory_rules_agent,         "Rules Agent")
        compiler.compile_system_prompt(stop_point_agent,           "Stop Point Agent")

        # Write compiled prompts to ./tmp for debugging
        os.makedirs("./tmp", exist_ok=True)
        for agent_id, agent in self.AGENTS.items():
            path = f"./tmp/system_prompt_{agent.name.replace(' ', '_')}.md"
            with open(path, "w", encoding="utf-8") as f:
                if isinstance(agent, ImageAgent):
                    f.write(f"Positive: {agent.positive_keywords}\n")
                    f.write(f"Negative: {agent.negative_keywords}\n")
                    f.write(f"Style: {agent.style}\n")
                else:
                    f.write(agent.system_prompt)

    # ══════════════════════════════════════════════════════════════════════════
    # LOW-LEVEL AGENT CALLS
    # One function per agent. No side effects on self.STORY.
    # ══════════════════════════════════════════════════════════════════════════

    def _build_world_state_header(self) -> str:
        """Shared context block injected into most agent prompts."""
        return (
            f"# World State\n"
            f"## Turn Number\n{self.STORY.turn_number}\n"
            f"## Persistent Facts\n{self.STORY.memory}\n"
            f"## Inventory\n{self.STORY.inventory}\n"
            f"## Time Since Last Turn\n{self.STORY.last_time_est}\n"
        )

    async def _call_writer(self, prompt: str, past_messages: str) -> str:
        """Run the writer agent non-streaming. Returns the full scene string."""
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"# Story So Far\n{past_messages}\n"
            f"---\n"
            f"## Planner Note\n{self.STORY.plan or 'No planner note yet.'}\n"
            f"---\n"
            f"## Player Input\n{prompt}\n"
        )
        return await self.AGENTS[WRITER_ID].generate_text_in_background(hydrated, temperature=1.0)

    async def _stream_writer(self, prompt: str, past_messages: str, stop_point: str):
        """Stream the writer agent response. Yields str chunks."""
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"# Story So Far\n{past_messages}\n"
            f"---\n"
            f"## Stop Point\n{stop_point}\n"
            f"---\n"
            f"## Planner Note\n{self.STORY.plan or 'No planner note yet.'}\n"
            f"---\n"
            f"## Player Input\n{prompt}\n"
        )
        async for chunk in self.AGENTS[WRITER_ID].stream_text(hydrated, temperature=1.0):
            if chunk is not None:
                yield chunk

    async def _call_checker_restraint(self, writer_output: str) -> str:
        """Restraint continuity checker. Returns verdict string."""
        hydrated = (
            f"## Inventory\n{self.STORY.inventory}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n"
        )
        return await self.AGENTS[CHECKER_RESTRAINT_ID].generate_text_in_background(hydrated, temperature=0.0)

    async def _call_checker_world(self, writer_output: str, past_messages: str) -> str:
        """World continuity checker. Returns verdict string."""
        hydrated = (
            f"## Memory\n{self.STORY.memory}\n"
            f"---\n"
            f"## Recent Story\n{past_messages}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n"
        )
        return await self.AGENTS[CHECKER_WORLD_ID].generate_text_in_background(hydrated, temperature=0.0)

    async def _call_checker_character(self, writer_output: str, past_messages: str) -> str:
        """Character continuity checker. Returns verdict string."""
        hydrated = (
            f"## Memory\n{self.STORY.memory}\n"
            f"---\n"
            f"## Recent Story\n{past_messages}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n"
        )
        return await self.AGENTS[CHECKER_CHARACTER_ID].generate_text_in_background(hydrated, temperature=0.0)

    async def _call_checker_memory(self, writer_output: str) -> str:
        """Memory continuity checker. Returns verdict string."""
        hydrated = (
            f"## Memory\n{self.STORY.memory}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n"
        )
        return await self.AGENTS[CHECKER_MEMORY_ID].generate_text_in_background(hydrated, temperature=0.0)

    async def _call_fixer(
        self,
        writer_output: str,
        check_restraint: str,
        check_world: str,
        check_character: str,
        check_memory: str,
    ) -> str:
        """Fixer agent. Returns corrected scene string (full fixer output including fix log)."""
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"## Original Output\n{writer_output}\n"
            f"---\n"
            f"## Restraint Check\n{check_restraint}\n"
            f"---\n"
            f"## World Check\n{check_world}\n"
            f"---\n"
            f"## Character Check\n{check_character}\n"
            f"---\n"
            f"## Memory Check\n{check_memory}\n"
        )
        return await self.AGENTS[FIXER_ID].generate_text_in_background(hydrated, temperature=0.5)

    # ── Window-based fixer helpers ───────────────────────────────────────────

    def _extract_violations(self, *checker_results: str) -> list[str]:
        """
        Parse all checker reports and return a list of quoted LOCATION strings —
        the exact offending text the checker pulled from the writer output.
        These are used to locate the repair window in the original text.
        """
        violations = []
        for report in checker_results:
            for line in report.splitlines():
                stripped = line.strip()
                if stripped.upper().startswith("LOCATION:"):
                    quoted = stripped.split(":", 1)[1].strip().strip('"\'`')
                    if quoted:
                        violations.append(quoted)
        return violations

    def _extract_repair_window(
        self, original: str, offending: str, context_sentences: int = 1
    ) -> tuple[str, str, str] | None:
        """
        Locate `offending` text in `original` and return (before, window, after)
        where window contains the offending text plus `context_sentences` of
        surrounding prose on each side as anchoring context.

        Returns None if the offending text cannot be located.
        """
        idx = original.find(offending)
        if idx == -1:
            # Try a fuzzy fallback — find best matching sentence
            sentences = re.split(r'(?<=[.!?])\s+', original)
            best_idx, best_ratio = -1, 0.0
            for i, s in enumerate(sentences):
                ratio = sum(1 for a, b in zip(s, offending) if a == b) / max(len(s), len(offending), 1)
                if ratio > best_ratio:
                    best_ratio, best_idx = ratio, i
            if best_ratio < 0.5 or best_idx == -1:
                return None
            # Reconstruct idx from sentence position
            running = 0
            for i, s in enumerate(sentences):
                if i == best_idx:
                    idx = original.find(s, running)
                    offending = s
                    break
                running += len(s) + 1

        # Split original into sentences, find which ones overlap the offending span
        sentence_spans = [(m.start(), m.end()) for m in re.finditer(r'[^.!?]+[.!?]+', original)]
        if not sentence_spans:
            return original[:idx], offending, original[idx + len(offending):]

        offend_end = idx + len(offending)
        overlapping = [
            i for i, (s, e) in enumerate(sentence_spans)
            if s < offend_end and e > idx
        ]
        if not overlapping:
            return original[:idx], offending, original[idx + len(offending):]

        first = max(0, overlapping[0] - context_sentences)
        last  = min(len(sentence_spans) - 1, overlapping[-1] + context_sentences)

        window_start = sentence_spans[first][0]
        window_end   = sentence_spans[last][1]

        return original[:window_start], original[window_start:window_end], original[window_end:]

    async def _call_window_fixer(
        self, window: str, violation_description: str
    ) -> str:
        """
        Send a single repair window to the fixer. The fixer returns only the
        corrected passage — no scene header, no fix log.
        """
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"## Passage To Fix\n{window}\n"
            f"---\n"
            f"## Violation\n{violation_description}\n"
            f"---\n"
            f"Return ONLY the corrected passage. No preamble, no fix log, no explanation. "
            f"Match the length and register of the original passage as closely as possible.\n"
        )
        return await self.AGENTS[FIXER_ID].generate_text_in_background(hydrated, temperature=0.5)

    def _compute_diff_events(self, original: str, corrected: str) -> list[dict]:
        """
        Word-level diff between original and corrected text.
        Returns {"op": "equal|delete|insert", "text": "..."} events for the frontend.
        Whitespace tokens are always emitted as equal ops to prevent words merging.
        """
        # Split into alternating [word, space, word, space...] tokens
        # re.split with a capturing group keeps the separators in the list
        def tokenize(text):
            return re.split(r'(\s+)', text)

        orig_tokens = tokenize(original)
        corr_tokens = tokenize(corrected)
        matcher = difflib.SequenceMatcher(None, orig_tokens, corr_tokens, autojunk=False)
        events = []

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            orig_chunk = orig_tokens[i1:i2]
            corr_chunk = corr_tokens[j1:j2]

            if op == "equal":
                events.append({"op": "equal", "text": "".join(orig_chunk)})

            elif op == "delete":
                # Emit word tokens as deletes, but keep whitespace tokens as equal
                # so surrounding words don't merge when deletes are hidden
                for token in orig_chunk:
                    if re.match(r'^\s+$', token):
                        events.append({"op": "equal",  "text": token})
                    else:
                        events.append({"op": "delete", "text": token})

            elif op == "insert":
                events.append({"op": "insert", "text": "".join(corr_chunk)})

            elif op == "replace":
                # Drop the old words, keep any whitespace, add new words
                for token in orig_chunk:
                    if re.match(r'^\s+$', token):
                        events.append({"op": "equal",  "text": token})
                    else:
                        events.append({"op": "delete", "text": token})
                # Insert new content — strip leading/trailing space since we kept orig spacing
                events.append({"op": "insert", "text": "".join(corr_chunk).strip()})

        return events

    async def _call_planner(self, past_messages: str) -> str:
        """Planner agent. Returns a soft narrative note string."""
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"## Recent Story\n{past_messages}\n"
        )
        return await self.AGENTS[PLANNER_ID].generate_text_in_background(hydrated, temperature=0.7)
    
    
    async def _call_memory_events(self, writer_output: str) -> list[str]:
        """
        Events agent — append only.
        Returns a list of new event strings to extend self.STORY.memory.events.
        Returns an empty list if nothing worth recording happened.
        """
        result = await self.AGENTS[MEMORY_EVENTS_ID].generate_text_in_background(
            f"[WRITER OUTPUT]\n{writer_output}",
            temperature=0.3,
        )
        result = result.strip()
        if not result or result.upper() == "NO_EVENTS":
            return []
        # Parse "- <event>" lines into plain strings
        events = []
        for line in result.splitlines():
            line = line.strip().lstrip("-").strip()
            if line:
                events.append(line)
        return events
 
    async def _call_memory_facts(self, writer_output: str) -> list[str]:
        """
        Facts agent — append only.
        Returns a list of new fact strings to extend self.STORY.memory.facts.
        Returns an empty list if no new facts were established.
        """
        result = await self.AGENTS[MEMORY_FACTS_ID].generate_text_in_background(
            f"[WRITER OUTPUT]\n{writer_output}",
            temperature=0.1,
        )
        result = result.strip()
        if not result or result.upper() == "NO_FACTS":
            return []
        facts = []
        for line in result.splitlines():
            line = line.strip().lstrip("-").strip()
            if line:
                facts.append(line)
        return facts
 
    async def _call_memory_characters(self, writer_output: str) -> str:
        """
        Characters agent — update in place.
        Returns the full updated [CHARACTERS] block as a string.
        """
        return await self.AGENTS[MEMORY_CHARACTER_ID].generate_text_in_background(
            f"[CHARACTERS]\n{self.STORY.memory.characters_raw}\n\n"
            f"[WRITER OUTPUT]\n{writer_output}",
            temperature=0.3,
        )
 
    async def _call_memory_current_state(self, writer_output: str) -> str:
        """
        Current state agent — full rewrite each turn.
        Returns the updated [CURRENT STATE] block as a string.
        """
        return await self.AGENTS[MEMORY_CURRENT_STATE_ID].generate_text_in_background(
            f"[CURRENT STATE]\n{self.STORY.memory.current_state}\n\n"
            f"[WRITER OUTPUT]\n{writer_output}",
            temperature=0.3,
        )
    
    async def _call_get_stop_point(self, writer_output: str, prompt: str) -> str:
        """
        Stop point agent — identifies a safe point in the text for the fixer to splice in corrections.
        Returns a single sentence string representing the stop point.
        """
        return await self.AGENTS[STOP_POINT_AGENT].generate_text_in_background(
            f"[PLAYER INPUT]\n{prompt}\n"
            f"[LAST OUTPUT]\n{writer_output}\n",
            temperature=0.3,
        )
 
    async def _call_memory_rules(self, writer_output: str) -> str:
        """
        Rules & routines agent — full rewrite each turn.
        Returns the updated [RULES & ROUTINES] block as a string.
        """
        return await self.AGENTS[MEMORY_RULES_ID].generate_text_in_background(
            f"[RULES & ROUTINES]\n{self.STORY.memory.rules}\n\n"
            f"[WRITER OUTPUT]\n{writer_output}",
            temperature=0.1,
        )
 
    async def _call_memory_update(self, writer_output: str) -> None:
        """
        Orchestrates all five memory agents concurrently.
        Current state runs every turn.
        Events, facts, characters, and rules run every turn but are cheap
        (events/facts return NO_EVENTS/NO_FACTS most turns).
        Writes results directly back to self.STORY.memory.
        """
        current_state, events, facts, characters, rules = await asyncio.gather(
            self._call_memory_current_state(writer_output),
            self._call_memory_events(writer_output),
            self._call_memory_facts(writer_output),
            self._call_memory_characters(writer_output),
            self._call_memory_rules(writer_output),
        )
 
        self.STORY.memory.current_state   = current_state
        self.STORY.memory.rules           = rules
        self.STORY.memory.characters_raw  = characters
 
        if events:
            self.STORY.memory.events.extend(events)
            print(f"[Memory] {len(events)} new event(s) appended")
 
        if facts:
            self.STORY.memory.facts.extend(facts)
            print(f"[Memory] {len(facts)} new fact(s) appended")
 
        print("[Memory] All sections updated")

    async def _call_inventory_update(self, writer_output: str) -> str:
        """Inventory agent. Returns updated inventory string."""
        return await self.AGENTS[INVENTORY_ID].generate_text_in_background(
            f"## Current Inventory\n{self.STORY.inventory}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n"
            f'## Last Time Estimate and Time\n{self.STORY.last_time_est}\n',
            temperature=0.1,
        )

    async def _call_time_update(self, writer_output: str) -> str:
        """Time estimation agent. Returns time-elapsed string."""
        return await self.AGENTS[TIME_ID].generate_text_in_background(
            f"## Writer Output\n{writer_output}\n"
            f"## Last Time Estimate and Time\n{self.STORY.last_time_est}\n",
            temperature=0.1,
        )


    # ══════════════════════════════════════════════════════════════════════════
    # HIGH-LEVEL PIPELINE FUNCTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _any_violation(self, *checker_results: str) -> bool:
        """Return True if any checker result contains a VIOLATION."""
        return any("VIOLATION" in r.upper() for r in checker_results)

    def _extract_corrected_output(self, fixer_output: str) -> str:
        """
        Pull just the [CORRECTED OUTPUT] block from fixer output,
        stripping the [FIX LOG] so only clean prose reaches the player.
        """
        if "[CORRECTED OUTPUT]" not in fixer_output:
            return fixer_output  # Fixer didn't follow format — use raw output
        corrected = fixer_output.split("[CORRECTED OUTPUT]", 1)[1]
        if "[FIX LOG]" in corrected:
            corrected = corrected.split("[FIX LOG]", 1)[0]
        return corrected.strip()

    async def _run_checkers(
        self, writer_output: str, past_messages: str
    ) -> tuple[str, str, str, str]:
        """
        Run all four continuity checkers in parallel.
        Returns (restraint, world, character, memory) verdict strings.
        """
        print("[Checkers] Running in parallel")
        results = await asyncio.gather(
            self._call_checker_restraint(writer_output),
            self._call_checker_world(writer_output, past_messages),
            self._call_checker_character(writer_output, past_messages),
            self._call_checker_memory(writer_output), 
        )
        passed = sum(1 for r in results if "PASS" in r.upper())
        print(f"[Checkers] {passed}/4 passed")
        return results  # (restraint, world, character, memory)

    async def _apply_fix_if_needed(
        self,
        writer_output: str,
        check_restraint: str,
        check_world: str,
        check_character: str,
        check_memory: str,
    ):
        """
        If any checker found a violation:
          1. Extract quoted offending text from all checker reports
          2. For each violation, cut a repair window (offending + context sentences)
          3. Fix each window in reverse order (back-to-front) so:
             - The player sees corrections landing in text ahead of where they're reading
             - Splice offsets are not shifted by earlier edits
          4. Diff the final corrected text against the original
          5. Yield diff events as newline-delimited JSON for the frontend

        Yields nothing if no violations found.
        self._last_fix_output holds the fully corrected text for story commit.
        """
        self._last_fix_output: str | None = None

        if not self._any_violation(check_restraint, check_world, check_character, check_memory):
            print("[Fixer] All clear — no fix needed")
            return

        violations = self._extract_violations(
            check_restraint, check_world, check_character, check_memory
        )
        if not violations:
            print("[Fixer] Violations flagged but no LOCATION quotes found — skipping")
            return

        print(f"[Fixer] {len(violations)} violation(s) — fixing windows back-to-front")

        # Build (position, offending, description) tuples and sort descending by position
        # so back-of-text edits land first and don't shift earlier splice anchors
        all_reports = "\n".join([check_restraint, check_world, check_character, check_memory])
        located = []
        for offending in violations:
            idx = writer_output.find(offending)
            if idx == -1:
                idx = len(writer_output)  # fallback: treat as end-of-text
            located.append((idx, offending))
        located.sort(key=lambda x: x[0], reverse=True)

        working = writer_output
        for position, offending in located:
            result = self._extract_repair_window(working, offending)
            if result is None:
                print(f"[Fixer] Could not locate window for: {offending[:60]}... — skipping")
                continue
            before, window, after = result
            corrected_window = await self._call_window_fixer(window, all_reports)
            corrected_window = corrected_window.strip()
            working = before + corrected_window + after
            print(f"[Fixer] Window repaired at position {position}")

        self._last_fix_output = working
        self.AGENTS[FIXER_ID].write_last_response_to_file()

        # Diff original vs fully corrected and stream events to client
        events = self._compute_diff_events(writer_output, working)
        print(f"[Fixer] Diff ready — {len(events)} events")
        yield json.dumps({"op": "diff_start"}) + "\n"
        for event in events:
            yield json.dumps(event) + "\n"

    async def _cache_planner_note(self, past_messages_with_output: str):
        """
        Run the planner against the just-completed turn and cache its note.
        Called in parallel with the checkers so it's ready before the next player input.
        """
        self.STORY.plan = await self._call_planner(past_messages_with_output)
        print("[Planner] Note cached for next turn")

    async def _update_background_data(self, final_output: str):
        print("[Background] Updating state")

        time_est    = await self._call_time_update(final_output)
        self.STORY.last_time_est = time_est

        memory_task   = asyncio.create_task(self._call_memory_update(final_output))
        inventory_task = asyncio.create_task(self._call_inventory_update(final_output))
        _, inventory = await asyncio.gather(
            memory_task, inventory_task,
        )

        self.STORY.inventory = inventory

        for agent in self.AGENTS.values():
            agent.write_last_response_to_file()

        print("[Background] State saved")

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    async def stream_response(self, prompt: str):
        """
        Full turn pipeline. Yields str chunks for the client.

        Timeline:
          1. Stream writer output to client
          2. Writer done → fire background update, checkers, and planner all simultaneously
          3. Await checkers → if violation, stream fixer correction to client
          4. Commit final message to story
          (Background update and planner run concurrently throughout steps 3-4)
        """
        past_messages = "\n".join([f"{m.agent_name}: {m.content}" for m in self.STORY.messages[-10:]])
        self.STORY.messages.append(Message("User", prompt))

        writer_output = ""
        # ── 1. Stop point ───────────────────────────────────────────────────
        stop_point = await self._call_get_stop_point(self.STORY.messages[-1], prompt)

        # ── 2. Stream writer ───────────────────────────────────────────────────
        try:
            async for chunk in self._stream_writer(prompt, past_messages, stop_point):
                writer_output += chunk
                yield chunk
        except Exception as e:
            traceback.print_exc()
            yield f"\n\n[Writer error: {str(e)}]"
            return

        # ── 3. Fire background + checkers + planner all at once ──────────────
        # Background data only needs writer_output and can run immediately.
        # Any fix from the fixer will be caught by the checkers next turn.
        print("[Pipeline] Writer done — background, checkers, and planner all starting")
        past_with_output = past_messages + f"\nWriter Agent: {writer_output}"

        background_task = asyncio.create_task(self._update_background_data(writer_output))
        checker_task    = asyncio.create_task(self._run_checkers(writer_output, past_messages))
        planner_task    = asyncio.create_task(self._cache_planner_note(past_with_output))

        # Checkers must finish before we can decide whether to fix
        await checker_task
        check_restraint, check_world, check_character, check_memory = checker_task.result()

        # Planner runs in parallel with checkers — await to ensure it's cached
        # before the next player input arrives (best-effort; won't block the client)
        asyncio.create_task(_ensure(planner_task))

        # ── 4. Apply window fixes and stream diff events ─────────────────────
        # Each yielded line is newline-delimited JSON.
        # {"op": "diff_start"} signals the client to switch to diff mode.
        # Subsequent ops update the message in place, back-to-front.
        async for event_line in self._apply_fix_if_needed(
            writer_output, check_restraint, check_world, check_character, check_memory
        ):
            yield event_line

        final_output = self._last_fix_output if self._last_fix_output is not None else writer_output

        # ── 5. Commit to story ─────────────────────────────────────────────────
        self.STORY.messages.append(Message(self.AGENTS[WRITER_ID].name, final_output))
        self.STORY.save()

        usage = self.AGENTS[WRITER_ID].last_usage
        if usage and usage.get("context_pct", 0) > 50:
            self.STORY.message_cutoff_index += 1

        self.STORY.turn_number += 1
        # background_task is already running — nothing more to schedule