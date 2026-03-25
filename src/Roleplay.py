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
WRITER_ID            = "writer_agent"
PLANNER_ID           = "planner_agent"
CHECKER_RESTRAINT_ID = "checker_restraint"
CHECKER_WORLD_ID     = "checker_world"
CHECKER_CHARACTER_ID = "checker_character"
CHECKER_MEMORY_ID    = "checker_memory"
FIXER_ID             = "fixer_agent"
MEMORY_ID            = "memory_agent"
INVENTORY_ID         = "inventory_agent"
TIME_ID              = "time_estimation_agent"


async def _ensure(task: asyncio.Task):
    """Await a task silently — used to let fire-and-forget tasks complete
    without blocking the caller if they haven't finished yet."""
    try:
        await task
    except Exception:
        pass


class Roleplay():
    def __init__(self, selected_story_directory, saves_dir, load_path = None):


        # ── Story ──────────────────────────────────────────────────────────────
        if load_path is not None and not os.path.exists(load_path):
                raise FileNotFoundError(f"Load path {load_path} does not exist")
        
        if load_path is None:
            self.STORY = Story(selected_story_directory)
            self.load_path = os.path.join(saves_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.STORY.title}.json")
        else:
            self.STORY = Story(selected_story_directory)
            self.STORY.load(load_path)
            self.load_path = load_path

        self.COMPRESSION_TURN = self.STORY.config.get("compression_turn", 20)
        self.IMAGE_GENERATION_ENABLED = False



        # ── Connectors ────────────────────────────────────────────────────────
        deep = DeepSeekAPIConnector()

        # ── Agents ────────────────────────────────────────────────────────────
        writer_agent            = TextAgent(WRITER_ID,            "Writer Agent",          "", deep)
        planner_agent           = TextAgent(PLANNER_ID,           "Planner Agent",         "", deep)
        checker_restraint_agent = TextAgent(CHECKER_RESTRAINT_ID, "Restraint Checker",     "", deep)
        checker_world_agent     = TextAgent(CHECKER_WORLD_ID,     "World Checker",         "", deep)
        checker_character_agent = TextAgent(CHECKER_CHARACTER_ID, "Character Checker",     "", deep)
        checker_memory_agent    = TextAgent(CHECKER_MEMORY_ID,    "Memory Checker",        "", deep)
        fixer_agent             = TextAgent(FIXER_ID,             "Fixer Agent",           "", deep)
        memory_agent            = TextAgent(MEMORY_ID,            "Memory Agent",          "", deep)
        inventory_agent         = TextAgent(INVENTORY_ID,         "Inventory Agent",       "", deep)
        time_estimation_agent   = TextAgent(TIME_ID,              "Time Estimation Agent", "", deep)

        self.AGENTS = {
            WRITER_ID:            writer_agent,
            CHECKER_RESTRAINT_ID: checker_restraint_agent,
            CHECKER_WORLD_ID:     checker_world_agent,
            CHECKER_CHARACTER_ID: checker_character_agent,
            CHECKER_MEMORY_ID:    checker_memory_agent,
            MEMORY_ID:            memory_agent,
            INVENTORY_ID:         inventory_agent,
            TIME_ID:              time_estimation_agent,
            PLANNER_ID:           planner_agent,
            FIXER_ID:             fixer_agent,
        }

        # ── System prompt compilation ──────────────────────────────────────────
        compiler = SystemPromptCompiler()
        compiler.import_system_prompt(self.STORY.story_template_path)
        compiler.compile_system_prompt(writer_agent,            "Writer Agent")
        compiler.compile_system_prompt(planner_agent,           "Planner Agent")
        compiler.compile_system_prompt(checker_restraint_agent, "Restraint Checker")
        compiler.compile_system_prompt(checker_world_agent,     "World Checker")
        compiler.compile_system_prompt(checker_character_agent, "Character Checker")
        compiler.compile_system_prompt(checker_memory_agent,    "Memory Checker")
        compiler.compile_system_prompt(fixer_agent,             "Fixer Agent")
        compiler.compile_system_prompt(memory_agent,            "Memory Agent")
        compiler.compile_system_prompt(inventory_agent,         "Inventory Manager")
        compiler.compile_system_prompt(time_estimation_agent,   "Time Estimator")

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
            f"## Planner Note\n{self.STORY.base_plan or 'No planner note yet.'}\n"
            f"---\n"
            f"## Player Input\n{prompt}\n"
        )
        return await self.AGENTS[WRITER_ID].generate_text_in_background(hydrated, temperature=1.0)

    async def _stream_writer(self, prompt: str, past_messages: str):
        """Stream the writer agent response. Yields str chunks."""
        hydrated = (
            f"{self._build_world_state_header()}"
            f"---\n"
            f"# Story So Far\n{past_messages}\n"
            f"---\n"
            f"## Planner Note\n{self.STORY.base_plan or 'No planner note yet.'}\n"
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

    async def _call_memory_update(self, new_information: str) -> str:
        """Memory agent. Returns updated memory string."""
        amnt = max(self.COMPRESSION_TURN * 2, 20)
        recent = self.STORY.messages[-amnt:]
        messages_text = "\n".join(f"{m.agent_name}: {m.content}" for m in recent)
        return await self.AGENTS[MEMORY_ID].generate_text_in_background(
            f"Current memory:\n{self.STORY.memory}\n\n"
            f"Past messages:\n{messages_text}\n\n"
            f"New information:\n{new_information}\n\n"
            f"Update the memory with the new information, keeping it concise and relevant.",
            temperature=0.5,
        )

    async def _call_inventory_update(self, writer_output: str) -> str:
        """Inventory agent. Returns updated inventory string."""
        return await self.AGENTS[INVENTORY_ID].generate_text_in_background(
            f"## Current Inventory\n{self.STORY.inventory}\n"
            f"---\n"
            f"## Writer Output\n{writer_output}\n",
            temperature=0.1,
        )

    async def _call_time_update(self, writer_output: str) -> str:
        """Time estimation agent. Returns time-elapsed string."""
        return await self.AGENTS[TIME_ID].generate_text_in_background(
            f"## Writer Output\n{writer_output}\n",
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
        self._last_fix_output = None

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
        self.STORY.base_plan = await self._call_planner(past_messages_with_output)
        print("[Planner] Note cached for next turn")

    async def _update_background_data(self, final_output: str):
        """
        Fire-and-forget background task that runs after each turn:
        - Updates memory (compression turns only), inventory, and time in parallel
        - Saves story state to disk
        - Pre-warms the planner note for the turn after next
        """
        if self.STORY.turn_number % self.COMPRESSION_TURN == 0:
            memory_coro = self._call_memory_update(final_output)
        else:
            async def _passthrough(): return self.STORY.memory
            memory_coro = _passthrough()

        print("[Background] Updating state")
        memory, inventory, time_est = await asyncio.gather(
            memory_coro,
            self._call_inventory_update(final_output),
            self._call_time_update(final_output),
        )

        for agent in self.AGENTS.values():
            agent.write_last_response_to_file()

        self.STORY.memory        = memory
        self.STORY.inventory     = inventory
        self.STORY.last_time_est = time_est

        print("[Background] State saved")
        # Planner pre-warm is handled by _cache_planner_note running in parallel


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
        past_messages = "\n".join([f"{m.agent_name}: {m.content}" for m in self.STORY.messages[-5:]])
        self.STORY.messages.append(Message("User", prompt))

        writer_output = ""

        # ── 1. Stream writer ───────────────────────────────────────────────────
        try:
            async for chunk in self._stream_writer(prompt, past_messages):
                writer_output += chunk
                yield chunk
        except Exception as e:
            traceback.print_exc()
            yield f"\n\n[Writer error: {str(e)}]"
            return

        # ── 2. Fire background + checkers + planner all at once ──────────────
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

        # ── 3. Apply window fixes and stream diff events ─────────────────────
        # Each yielded line is newline-delimited JSON.
        # {"op": "diff_start"} signals the client to switch to diff mode.
        # Subsequent ops update the message in place, back-to-front.
        fix_applied = False
        async for event_line in self._apply_fix_if_needed(
            writer_output, check_restraint, check_world, check_character, check_memory
        ):
            fix_applied = True
            yield event_line

        final_output = self._last_fix_output if fix_applied else writer_output

        # ── 4. Commit to story ─────────────────────────────────────────────────
        self.STORY.messages.append(Message(self.AGENTS[WRITER_ID].name, final_output))
        self.STORY.save(self.load_path)

        usage = self.AGENTS[WRITER_ID].last_usage
        if usage and usage.get("context_pct", 0) > 50:
            self.STORY.message_cutoff_index += 1

        self.STORY.turn_number += 1
        # background_task is already running — nothing more to schedule