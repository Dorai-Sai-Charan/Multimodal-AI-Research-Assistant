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

MAX_ITERATIONS = 10  # prevents runaway loops


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
            "get_paper_preview": self.tools.get_paper_preview,
            "get_paper_list": self.tools.get_paper_list,
        }
        self.tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "Search textual content in uploaded research papers. Best for finding general information, methodology, and results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query focusing on natural language text."},
                            "source_file": {"type": "string", "description": "Optional specific filename to search within."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_tables",
                    "description": "Search for data and statistics specifically inside tables of uploaded papers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query focusing on data/numerical values."},
                            "source_file": {"type": "string", "description": "Optional specific filename to search within."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_figures",
                    "description": "Search descriptions and metadata of figures, charts, and diagrams.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for visual elements."},
                            "source_file": {"type": "string", "description": "Optional specific filename to search within."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_equations",
                    "description": "Search for mathematical formulas and their explanations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "LaTeX symbols or natural language description of an equation."},
                            "source_file": {"type": "string", "description": "Optional specific filename to search within."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_paper_preview",
                    "description": "Fetch the first few sections/chunks of a research paper. Best for finding Title, Authors, Abstract, and Introduction.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_file": {"type": "string", "description": "The exact filename of the paper to preview."},
                        },
                        "required": ["source_file"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_paper_list",
                    "description": "List all available research papers currently in the database.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": "Provide the final answer to the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string", "description": "The complete final answer with citations."},
                        },
                        "required": ["answer"],
                    },
                },
            },
        ]

    def run(
        self,
        question: str,
        chat_history: list[dict] | None = None,
        llm_config: dict | None = None,
        filter_source: str | None = None,
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
        
        # Inject focus paper context if provided
        focus_info = ""
        if filter_source:
            focus_info = f"\n[CONTEXT] The user is currently focused on the paper: {filter_source}. Refer to this paper when the user says 'this paper' or 'this document'.\n"
            
        prompt = AGENT_PROMPT.format(
            question=question, 
            history=history_text
        )
        if focus_info:
            prompt = focus_info + prompt

        steps: list[AgentStep] = []
        all_observation_text = ""
        citations_list: list[dict] = []

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"Agent iteration {iteration + 1}/{MAX_ITERATIONS}")

            # 1. Generate next step (including tools)
            response_msg = self.llm.generate(
                prompt, 
                temperature=0.1, 
                max_tokens=1024, 
                llm_config=llm_config,
                tools=self.tool_schemas,
                tool_choice="auto"
            )

            # If it's a string, something went wrong or it's a plain text response
            if isinstance(response_msg, str):
                logger.warning(f"Unexpected string response: {response_msg}")
                return AgentResponse(
                    answer=response_msg,
                    query=question,
                    intent="multi_hop_qa",
                )

            thought = response_msg.content or "Analyzing..."
            tool_calls = response_msg.tool_calls

            logger.info(f"  Thought: {thought[:120]}...")

            # ---- handle action extraction -----------------------------------
            action = ""
            action_input = {}

            if tool_calls:
                # 1. Preferred: Native tool calling
                tool_call = tool_calls[0]
                action = tool_call.function.name
                try:
                    action_input = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    action_input = {"raw_input": tool_call.function.arguments}
            else:
                # 2. Fallback: Parse text-based ReAct pattern (for smaller models like Llama)
                parsed_thought, parsed_action, parsed_input = self._parse(thought)
                if parsed_action:
                    thought = parsed_thought
                    action = parsed_action
                    action_input = parsed_input
                else:
                    # No tool call and no parsed action -> final answer
                    return AgentResponse(
                        answer=thought,
                        reasoning_steps=steps,
                        citations=citations_list,
                        query=question,
                        intent="multi_hop_qa",
                        chunks_used=len(steps),
                        total_steps=len(steps),
                    )

            # ---- handle finish action ---------------------------------------
            if action.lower() == "finish":
                final_answer = action_input.get("answer", thought)
                return AgentResponse(
                    answer=final_answer,
                    reasoning_steps=steps,
                    citations=citations_list,
                    query=question,
                    intent="multi_hop_qa",
                    chunks_used=len(steps),
                    total_steps=len(steps),
                )

            # ---- execute tools ----------------------------------------------
            logger.info(f"  Action:  {action}  Input: {action_input}")

            observation = self._execute(action, action_input)
            obs_truncated = observation[:2000] if len(observation) > 2000 else observation

            # Parse citation patterns from the observation string
            # Matches: [Paper: filename.pdf, Page: N] or [Paper: filename.pdf, Page N]
            citation_pattern = re.compile(
                r"\[Paper:\s*([^,\]]+?),\s*Page:?\s*(\d+)\]",
                re.IGNORECASE,
            )
            for match in citation_pattern.finditer(obs_truncated):
                source_file = match.group(1).strip()
                page_num = int(match.group(2))
                # Avoid duplicates
                entry = {"source_file": source_file, "page": page_num, "relevance": 1.0}
                if entry not in citations_list:
                    citations_list.append(entry)

            step = AgentStep(
                step_number=iteration + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=obs_truncated,
            )
            steps.append(step)

            # ---- extend prompt ---------------------------------------------
            # We manually update the prompt history so the model sees the previous turn
            prompt += (
                f"\nThought: {thought}\n"
                f"Action Call: {action}({json.dumps(action_input)})\n"
                f"Observation: {obs_truncated}\n"
            )

        # ---- max iterations reached or loop ended without finish ----------
        # If at least one observation returned useful content, synthesise a
        # final answer from what was retrieved rather than asking a question.
        useful_observations = [
            s.observation for s in steps
            if s.observation and "No relevant content found" not in s.observation
        ]

        if useful_observations:
            obs_context = "\n\n".join(useful_observations[:6])  # cap to avoid token overflow
            synthesis_prompt = (
                f"Based on the following retrieved information, answer the original "
                f"question as best you can.\n\n"
                f"ORIGINAL QUESTION: {question}\n\n"
                f"RETRIEVED INFORMATION:\n{obs_context}\n\n"
                f"ANSWER:"
            )
            answer = self.llm.generate(synthesis_prompt, temperature=0.2, llm_config=llm_config)
        else:
            # Nothing useful was found — ask for clarification
            answer = self._generate_clarification(question, steps, llm_config)

        return AgentResponse(
            answer=answer,
            reasoning_steps=steps,
            citations=citations_list,
            query=question,
            intent="multi_hop_qa",
            chunks_used=len(steps),
            total_steps=len(steps),
        )

    def _generate_clarification(
        self, 
        question: str, 
        steps: list[AgentStep], 
        llm_config: dict | None = None
    ) -> str:
        """Generate a clarifying question when the agent gets stuck."""
        from src.generation.prompts import AGENT_CLARIFICATION_PROMPT
        
        trace = ""
        for s in steps:
            trace += f"Step {s.step_number}: {s.thought}\n"
            trace += f"Action: {s.action}({json.dumps(s.action_input)})\n"
            trace += f"Observation: {s.observation[:500]}...\n\n"

        prompt = AGENT_CLARIFICATION_PROMPT.format(
            question=question,
            trace=trace
        )

        return self.llm.generate(
            prompt,
            temperature=0.7, # slightly higher for more natural questioning
            llm_config=llm_config
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> tuple[str, str, dict]:
        """Extract (thought, action, action_input) from a raw LLM response."""

        # Thought (everything before Action:)
        thought_m = re.search(r"^(.*?)(?=\n?Action:)", text, re.DOTALL | re.IGNORECASE)
        thought = thought_m.group(1).strip() if thought_m else text.strip()

        # Action name
        action_m = re.search(r"Action:\s*(\w+)", text, re.IGNORECASE)
        action = action_m.group(1).strip() if action_m else ""

        # Action Input (JSON object or string)
        input_m = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL | re.IGNORECASE)
        action_input: dict = {}
        if input_m:
            try:
                action_input = json.loads(input_m.group(1))
            except json.JSONDecodeError:
                # Fallback: check for "answer" if it's the finish action but poorly formatted
                ans_m = re.search(r'"answer"\s*:\s*"(.*?)"', input_m.group(1), re.DOTALL)
                if ans_m:
                    action_input = {"answer": ans_m.group(1)}
                else:
                    action_input = {"raw_input": input_m.group(1).strip()}

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
        """Format the last 8 messages as context for the agent."""
        if not history:
            return ""
        recent = history[-8:]
        lines = []
        for m in recent:
            role = m.get("role", "user").upper()
            content = str(m.get("content", ""))
            # Truncate per-message to keep prompt manageable
            if role == "ASSISTANT":
                content = content[:500]
            else:
                content = content[:300]
            lines.append(f"{role}: {content}")
        return "\nPrevious conversation:\n" + "\n".join(lines) + "\n"
