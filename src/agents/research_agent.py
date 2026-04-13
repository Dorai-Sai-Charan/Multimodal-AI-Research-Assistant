"""
ReAct-pattern Research Agent.

Implements the Thought → Action → Observation loop described in:
  "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022)
  "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG"

The agent can call multiple retrieval tools in sequence, enabling multi-hop reasoning
across text, tables, figures, and equations inside uploaded research papers.
"""

import re
import json
import logging
from src.agents.tools import AgentTools
from src.generation.llm_client import LLMClient
from src.generation.prompts import AGENT_PROMPT
from src.models.schemas import AgentStep, AgentResponse

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 6  # prevents runaway loops


class ResearchAgent:
    """
    ReAct agent for multi-hop research question answering.

    Loop:
        1. LLM generates Thought + Action + Action Input
        2. System executes the tool → Observation
        3. Observation is appended to the running prompt
        4. Repeat until the agent calls 'finish' or MAX_ITERATIONS is reached
    """

    def __init__(self):
        self.llm = LLMClient()
        self.tools = AgentTools()
        self._tool_map = {
            "search_text": self.tools.search_text,
            "search_tables": self.tools.search_tables,
            "search_figures": self.tools.search_figures,
            "search_equations": self.tools.search_equations,
            "get_paper_list": self.tools.get_paper_list,
        }

    def run(
        self,
        question: str,
        chat_history: list[dict] | None = None,
        llm_config: dict | None = None,
    ) -> AgentResponse:
        """
        Execute the ReAct loop for the given question.

        Args:
            question: User's natural-language question.
            chat_history: List of {"role": ..., "content": ...} dicts (last N turns).

        Returns:
            AgentResponse with the final answer and full reasoning trace.
        """
        history_text = self._format_history(chat_history or [])
        prompt = AGENT_PROMPT.format(question=question, history=history_text)

        steps: list[AgentStep] = []
        all_observation_text = ""

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"Agent iteration {iteration + 1}/{MAX_ITERATIONS}")

            raw = self.llm.generate(
                prompt, temperature=0.1, max_tokens=1024, llm_config=llm_config
            )
            thought, action, action_input = self._parse(raw)

            logger.info(f"  Thought: {thought[:120]}")
            logger.info(f"  Action:  {action}  Input: {action_input}")

            # ---- termination ------------------------------------------------
            if action.lower() == "finish":
                final_answer = action_input.get("answer", raw)
                return AgentResponse(
                    answer=final_answer,
                    reasoning_steps=steps,
                    citations=[],
                    query=question,
                    intent="multi_hop_qa",
                    chunks_used=len(steps),
                    total_steps=len(steps),
                )

            # ---- malformed output — treat whole response as answer ----------
            if not action:
                return AgentResponse(
                    answer=raw,
                    reasoning_steps=steps,
                    citations=[],
                    query=question,
                    intent="multi_hop_qa",
                    chunks_used=len(steps),
                    total_steps=len(steps),
                )

            # ---- execute tool -----------------------------------------------
            observation = self._execute(action, action_input)
            # Truncate to avoid blowing up the context window
            obs_truncated = observation[:1500] if len(observation) > 1500 else observation

            step = AgentStep(
                step_number=iteration + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=obs_truncated,
            )
            steps.append(step)
            all_observation_text += f"\n{obs_truncated}"

            # ---- extend prompt with this step so LLM sees its own history ---
            prompt += (
                f" {thought}\n"
                f"Action: {action}\n"
                f"Action Input: {json.dumps(action_input)}\n"
                f"Observation: {obs_truncated}\n"
                f"Thought:"
            )

        # ---- max iterations reached — force a final synthesis ---------------
        synthesis_prompt = (
            prompt
            + " I have gathered enough information from the papers. "
            "Let me write a comprehensive final answer.\n"
            "Action: finish\n"
            'Action Input: {"answer": "'
        )
        final_raw = self.llm.generate(
            synthesis_prompt, temperature=0.2, max_tokens=2048, llm_config=llm_config
        )
        # The model may or may not include the closing quote/brace — extract best effort
        final_answer = self._extract_finish_answer(final_raw)

        return AgentResponse(
            answer=final_answer,
            reasoning_steps=steps,
            citations=[],
            query=question,
            intent="multi_hop_qa",
            chunks_used=len(steps),
            total_steps=len(steps),
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> tuple[str, str, dict]:
        """Extract (thought, action, action_input) from a raw LLM response."""

        # Thought
        thought_m = re.search(r"^(.*?)(?=\nAction:)", text, re.DOTALL)
        thought = thought_m.group(1).strip() if thought_m else text.strip()

        # Action name
        action_m = re.search(r"\nAction:\s*(\w+)", text)
        action = action_m.group(1).strip() if action_m else ""

        # Action Input (JSON object)
        input_m = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
        action_input: dict = {}
        if input_m:
            try:
                action_input = json.loads(input_m.group(1))
            except json.JSONDecodeError:
                # Try to extract the "answer" string for the finish action
                ans_m = re.search(r'"answer"\s*:\s*"(.*?)"', input_m.group(1), re.DOTALL)
                if ans_m:
                    action_input = {"answer": ans_m.group(1)}

        return thought, action, action_input

    def _execute(self, action: str, action_input: dict) -> str:
        """Dispatch to the appropriate tool function."""
        fn = self._tool_map.get(action.lower())
        if fn is None:
            return (
                f"Unknown tool '{action}'. "
                f"Available tools: {list(self._tool_map.keys())}"
            )
        try:
            return fn(**action_input)
        except TypeError as e:
            return f"Invalid arguments for tool '{action}': {e}"
        except Exception as e:
            logger.error(f"Tool '{action}' raised an error: {e}")
            return f"Tool '{action}' encountered an error: {e}"

    def _extract_finish_answer(self, text: str) -> str:
        """Best-effort extraction of the answer from a finish action_input."""
        # If the model continued and produced finish naturally
        finish_m = re.search(r'"answer"\s*:\s*"(.*?)"', text, re.DOTALL)
        if finish_m:
            return finish_m.group(1).replace("\\n", "\n")
        # Otherwise return the raw text
        return text.strip()

    def _format_history(self, history: list[dict]) -> str:
        """Format the last 4 messages as context for the agent."""
        if not history:
            return ""
        recent = history[-4:]
        lines = [
            f"{m.get('role', 'user').upper()}: {str(m.get('content', ''))[:200]}"
            for m in recent
        ]
        return "\nPrevious conversation:\n" + "\n".join(lines) + "\n"
