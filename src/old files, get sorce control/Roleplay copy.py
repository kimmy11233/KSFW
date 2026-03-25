from src.Agent import ImageAgent, TextAgent, AgentStatus
from src.OpenRouterAPIConnector import OpenRouterAPIConnector
from src.SDUIConnector import SDUIConnector
from src.SystemPromptCompiler import SystemPromptCompiler
from src.DeepSeekConnector import DeepSeekAPIConnector
from src.Story import Message, Story

import asyncio
import os
import traceback
import os



class Roleplay():
    def __init__(self, selected_story_directory, load_path):

        self.selected_story_directory = selected_story_directory
        self.load_path = load_path

        # Initialize connectors
        orac = OpenRouterAPIConnector()
        deep = DeepSeekAPIConnector()
        deep_reasoner = DeepSeekAPIConnector(model="deepseek-reasoner")

        # Initialize agents
        planner_a_agent = TextAgent("planner_a_agent", "Planner Agent(Phase 1)", "", deep)
        planner_b_agent = TextAgent("planner_b_agent", "Planner Agent(Phase 2)", "", deep)
        main_agent = TextAgent("main_agent", "Story Architect", "", deep)
        memory_agent = TextAgent("memory_agent", "Memory Agent", "", deep)
        time_estimation_agent = TextAgent("time_estimation_agent", "Time Estimation Agent", "", deep)
        inventory_agent = TextAgent("inventory_agent", "Inventory Agent", "", deep)

        self.AGENTS = {
            planner_a_agent.id: planner_a_agent,
            planner_b_agent.id: planner_b_agent,
            main_agent.id: main_agent,
            memory_agent.id: memory_agent,
            time_estimation_agent.id: time_estimation_agent,
            inventory_agent.id: inventory_agent,
        }

        # Initialize the system prompt compiler
        system_prompt_compiler = SystemPromptCompiler()
        system_prompt_compiler.import_system_prompt(self.selected_story_directory)
        system_prompt_compiler.compile_system_prompt(planner_a_agent, "Planner Agent(Phase 1)")
        system_prompt_compiler.compile_system_prompt(planner_b_agent, "Planner Agent(Phase 2)")
        system_prompt_compiler.compile_system_prompt(main_agent, "Roleplay Agent")
        system_prompt_compiler.compile_system_prompt(memory_agent, "Memory Agent")
        system_prompt_compiler.compile_system_prompt(time_estimation_agent, "Time Estimator")
        system_prompt_compiler.compile_system_prompt(inventory_agent, "Inventory Manager")

        # Write compiled system prompts to ./tmp for debugging/inspection
        os.makedirs("./tmp", exist_ok=True)
        for agent_id, agent in self.AGENTS.items():
            with open(f"./tmp/system_prompt_{agent.name.replace(' ', '_')}.md", "w", encoding='utf-8') as f:
                if isinstance(agent, ImageAgent):
                    f.write(f"Positive: {agent.positive_keywords}\n")
                    f.write(f"Negative: {agent.negative_keywords}\n")
                    f.write(f"Style: {agent.style}\n")
                else:
                    f.write(agent.system_prompt)



        if os.path.exists(self.load_path):
            self.STORY = Story(self.selected_story_directory)
            self.STORY.load(self.load_path)
        else:
            self.STORY = Story(self.selected_story_directory)

        self.IMAGE_GENERATION_ENABLED = self.STORY.config.get("image_generation", False)
        self.COMPRESSION_TURN = self.STORY.config.get("compression_turn", 20)
        self.IMAGE_GENERATION_ENABLED = False



    def __restraint_changed(self, beat_plan: str) -> bool:
        """Return True if the beat plan signals a restraint state change."""
        for line in beat_plan.splitlines():
            if line.strip().upper().startswith("RESTRAINT_DELTA:"):
                value = line.split(":", 1)[-1].strip().upper()
                return value != "NO RESTRAINT CHANGE" and value != ""
        # If the field is missing, assume change to be safe
        return True


    async def __run_planner_a(self, last_beat_plan: str, last_prompt: str) -> str:
        """Run Phase A audit against current story state. Returns the audit string.

        Phase A does not need the writer's prose — it works from structured facts only:
        the updated memory/inventory/time, the beat plan that was executed last turn,
        and the player input that triggered it.
        """
        hydrated_planner_a = f"""
# World State
## Persistent Facts
{self.STORY.memory}
## Last Turn Time Estimation
{self.STORY.last_time_est}
## Inventory
{self.STORY.inventory}
---
# Last Turn
## Beat Plan Executed
{last_beat_plan}
## Player Input That Triggered It
{last_prompt}
"""
        return await self.AGENTS["planner_a_agent"].generate_text_in_background(hydrated_planner_a, temperature=0.2)


    async def __run_planner_b(self, prompt: str, past_messages: str, audit: str) -> str:
        """Run Phase B beat resolution given a valid Phase A audit."""
        hydrated_planner_b = f"""
## Phase A Audit
{audit}
---
# Recent Story
{past_messages}
---
## Player Input
{prompt}
    """
        return await self.AGENTS["planner_b_agent"].generate_text_in_background(hydrated_planner_b, temperature=0.2)



    async def __update_background_data(self, beat_plan: str, last_prompt: str, phase_a_audit: str):
        """
        Runs after each turn completes:
        - Updates memory, inventory, time estimate (all in parallel, from planner facts only)
        - Fires Phase A for the next turn in the background so it's cached and ready
        """

        if self.STORY.turn_number % self.COMPRESSION_TURN == 0:
            amnt_messages_to_include = max(self.COMPRESSION_TURN * 2, 20)
            recent_messages = self.STORY.messages[-amnt_messages_to_include:]
            messages_text = "\n".join(
                f"{msg.agent_name}: {msg.content}" for msg in recent_messages
            )
            memory_coro = self.AGENTS["memory_agent"].generate_text_in_background(
                f"Current memory:\n{self.STORY.memory}\n\nNew information:\n{messages_text}\n\nUpdate the memory with the new information, keeping it concise and relevant.",
                temperature=0.5
            )
        else:
            async def _passthrough(): return self.STORY.memory
            memory_coro = _passthrough()

        memory, inventory, time_estimation = await asyncio.gather(
            memory_coro,
            self.AGENTS["inventory_agent"].generate_text_in_background(
                f"## Current Inventory\n{self.STORY.inventory}\n---\n## Phase A Audit\n{phase_a_audit}\n---\n## Phase B Beat Plan\n{beat_plan}",
                temperature=0.1
            ),
            self.AGENTS["time_estimation_agent"].generate_text_in_background(
                f"## Phase B Beat Plan\n{beat_plan}",
                temperature=0.1
            ),
        )

        self.AGENTS["main_agent"].write_last_response_to_file()
        self.AGENTS["planner_a_agent"].write_last_response_to_file()
        self.AGENTS["planner_b_agent"].write_last_response_to_file()
        self.AGENTS["memory_agent"].write_last_response_to_file()
        self.AGENTS["time_estimation_agent"].write_last_response_to_file()
        self.AGENTS["inventory_agent"].write_last_response_to_file()

        self.STORY.memory = memory
        self.STORY.inventory = inventory
        self.STORY.last_time_est = time_estimation
        self.STORY.save(self.load_path)

        # Pre-warm Phase A using structured facts — no need to wait for writer prose
        print("[Planner] Pre-warming Phase A for next turn")
        self.STORY.base_plan = await self.__run_planner_a(beat_plan, last_prompt)
        self.STORY.base_plan_is_valid = True
        print("[Planner] Phase A cache ready")


    async def stream_response(self, prompt: str, past_messages: str, beat_plan: str):
        """Stream the writer response to the client.

        Background tasks are scheduled by the caller immediately after get_beat_plan()
        returns, so they run in parallel with this stream rather than after it.
        """

        try:
            hydrated_writer = f"""
# World State
## Persistent Facts
{self.STORY.memory}
## Inventory
{self.STORY.inventory}
---
# Story So Far
{past_messages}
---
## Beat Plan
{beat_plan}
"""
            async for chunk in self.AGENTS["main_agent"].stream_text(hydrated_writer, temperature=1.0):
                if chunk is not None:
                    yield chunk

            self.STORY.messages.append(Message(self.AGENTS["main_agent"].name, self.AGENTS["main_agent"].last_response))

            if self.AGENTS["main_agent"].last_usage['context_pct'] > 50:
                self.STORY.message_cutoff_index += 1

        except Exception as e:
            error_msg = f"\n\n[Error: {str(e)}]"
            print(f"Error generating story: {e}")
            traceback.print_exc()
            yield error_msg

        self.STORY.turn_number += 1



    async def get_beat_plan(self, prompt: str, past_messages: str) -> str:
        """
        Return a beat plan for the current player input.

        If a valid Phase A audit is cached, runs only Phase B (fast).
        If the cache is stale or empty, runs Phase A first, then Phase B.
        """

        if not self.STORY.base_plan_is_valid or not self.STORY.base_plan:
            print("[Planner] Cache miss — running Phase A before Phase B")
            # On a cache miss there is no prior beat plan yet; pass empty strings as a cold start
            self.STORY.base_plan = await self.__run_planner_a(
                last_beat_plan=self.STORY.base_plan or "",
                last_prompt=prompt,
            )
            self.STORY.base_plan_is_valid = True
        else:
            print("[Planner] Cache hit — skipping Phase A")

        return await self.__run_planner_b(prompt, past_messages, self.STORY.base_plan)