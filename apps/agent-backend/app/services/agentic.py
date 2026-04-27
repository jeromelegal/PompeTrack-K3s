from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents.prompts import (
    critic_system_prompt,
    critic_user_prompt,
    executor_system_prompt,
    executor_user_prompt,
    fallback_answer_system_prompt,
    fallback_answer_user_prompt,
    planner_system_prompt,
    planner_user_prompt,
    researcher_system_prompt,
    researcher_user_prompt,
)
from app.agents.schemas import CriticReview, ExecutorPlan, PlannerPlan, ResearchPlan
from app.agents.state import AgentState
from app.core.config import Settings

logger = logging.getLogger(__name__)


class AgenticService:
    def __init__(
        self,
        settings: Settings,
        ollama,
        websearch,
        scraper,
        workspace,
        rag,
        state_store,
    ) -> None:
        self.settings = settings
        self.ollama = ollama
        self.websearch = websearch
        self.scraper = scraper
        self.workspace = workspace
        self.rag = rag
        self.state_store = state_store

        self._checkpointer_cm = None
        self._checkpointer: AsyncSqliteSaver | None = None
        self.graph = None
        self._startup_lock = asyncio.Lock()

    async def startup(self) -> None:
        if self.graph is not None:
            return

        async with self._startup_lock:
            if self.graph is not None:
                return

            self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(
                self.settings.checkpoint_db_path
            )
            self._checkpointer = await self._checkpointer_cm.__aenter__()

            # Recommandé pour initialiser correctement la base de checkpoints
            if hasattr(self._checkpointer, "setup"):
                await self._checkpointer.setup()

            self.graph = self._build_graph()
            logger.info("AgenticService initialized with AsyncSqliteSaver")

    async def shutdown(self) -> None:
        async with self._startup_lock:
            if self._checkpointer_cm is not None:
                await self._checkpointer_cm.__aexit__(None, None, None)

            self._checkpointer_cm = None
            self._checkpointer = None
            self.graph = None
            logger.info("AgenticService shutdown complete")

    def _build_graph(self):
        if self._checkpointer is None:
            raise RuntimeError("Checkpointer not initialized. Call startup() first.")

        builder = StateGraph(AgentState)
        builder.add_node("planner", self._planner_node)
        builder.add_node("researcher", self._researcher_node)
        builder.add_node("executor", self._executor_node)
        builder.add_node("critic", self._critic_node)
        builder.add_edge(START, "planner")
        builder.add_edge("planner", "researcher")
        builder.add_edge("researcher", "executor")
        builder.add_edge("executor", "critic")
        builder.add_conditional_edges("critic", self._critic_router, {"planner": "planner", END: END})
        return builder.compile(checkpointer=self._checkpointer)

    async def healthcheck(self) -> dict[str, Any]:
        ollama_ok = await self.ollama.ping()
        searx_ok = await self.websearch.ping()
        rag_ok = self.rag.ping()
        overall = ollama_ok and searx_ok and rag_ok
        return {
            "status": "ok" if overall else "degraded",
            "services": {
                "ollama": ollama_ok,
                "searxng": searx_ok,
                "qdrant": rag_ok,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def openai_models_response(self) -> dict[str, Any]:
        models = await self.ollama.list_local_models()
        if not models:
            models = [{"name": self.settings.default_chat_model, "model": self.settings.default_chat_model}]
        data = [
            {
                "id": model.get("name") or model.get("model") or self.settings.default_chat_model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-agentic-stack",
            }
            for model in models
        ]
        return {"object": "list", "data": data}

    async def run_once(
        self,
        messages: list[dict[str, Any]],
        selected_model: str,
        session_id: str | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        parts: list[str] = []
        run_id: str | None = None
        async for chunk in self.run_streaming_text(messages, selected_model, session_id, user_id, capture_run_id=True):
            if isinstance(chunk, tuple):
                run_id = chunk[1]
                parts.append(chunk[0])
            else:
                parts.append(chunk)
        return {
            "run_id": run_id or f"run-{uuid.uuid4().hex}",
            "content": "".join(parts),
        }

    async def run_streaming_text(
        self,
        messages: list[dict[str, Any]],
        selected_model: str,
        session_id: str | None,
        user_id: str | None,
        capture_run_id: bool = False,
    ) -> AsyncGenerator[str | tuple[str, str], None]:
        if self.graph is None:
            await self.startup()

        if self.graph is None:
            raise RuntimeError("Agent graph is not initialized.")

        goal = self._extract_goal(messages)
        thread_id = session_id or user_id or f"session-{uuid.uuid4().hex}"
        run_id = f"run-{uuid.uuid4().hex}"

        self.state_store.create_run(
            run_id=run_id,
            session_id=thread_id,
            user_id=user_id,
            model=selected_model,
            goal=goal,
        )

        initial_state: AgentState = {
            "run_id": run_id,
            "session_id": thread_id,
            "user_id": user_id,
            "goal": goal,
            "messages": messages,
            "selected_model": selected_model,
            "iteration": 0,
            "max_iterations": self.settings.max_iterations,
            "plan": {},
            "research_plan": {},
            "critic": {},
            "gathered_context": [],
            "trace": [],
            "done": False,
            "final_answer": "",
            "stop_reason": "",
        }
        config = {"configurable": {"thread_id": thread_id}}
        last_trace_count = 0
        last_state: dict[str, Any] = dict(initial_state)

        if self.settings.show_trace_in_response:
            header = "### Trace d'exécution\n\n"
            if capture_run_id:
                yield (header, run_id)
            else:
                yield header

        async for state in self.graph.astream(initial_state, config=config, stream_mode="values"):
            last_state = state
            trace = state.get("trace", [])
            if len(trace) > last_trace_count:
                new_events = trace[last_trace_count:]
                last_trace_count = len(trace)
                if self.settings.show_trace_in_response:
                    for event in new_events:
                        line = f"- **{event.get('node', 'agent')}**: {event.get('summary', '')}\n"
                        if capture_run_id:
                            yield (line, run_id)
                            capture_run_id = False
                        else:
                            yield line
                await asyncio.sleep(0)

        final_answer = str(last_state.get("final_answer", "")).strip()
        stop_reason = str(last_state.get("stop_reason", "done")).strip() or "done"
        if not final_answer:
            final_answer = await self._compose_fallback_answer(last_state)

        self.state_store.finish_run(
            run_id=run_id,
            status="completed" if stop_reason != "failed" else "failed",
            stop_reason=stop_reason,
            final_answer=final_answer,
        )

        footer = f"\n### Réponse finale\n\n{final_answer}\n\n_Run ID: `{run_id}`_\n"
        if capture_run_id:
            yield (footer, run_id)
        else:
            for token in self._chunk_text(footer):
                yield token

    def _critic_router(self, state: AgentState):
        if state.get("done"):
            return END
        return "planner"

    async def _planner_node(self, state: AgentState) -> dict[str, Any]:
        plan = await self.ollama.structured_invoke(
            state["selected_model"],
            PlannerPlan,
            planner_system_prompt(),
            planner_user_prompt(state),
        )
        event = self._event("planner", plan.objective_summary, plan.model_dump())
        self.state_store.add_event(state["run_id"], "planner", event)
        return {"plan": plan.model_dump(), "trace": [event]}

    async def _researcher_node(self, state: AgentState) -> dict[str, Any]:
        research = await self.ollama.structured_invoke(
            state["selected_model"],
            ResearchPlan,
            researcher_system_prompt(),
            researcher_user_prompt(state),
        )
        summary = (
            f"{len(research.web_queries)} web query(ies), "
            f"{len(research.rag_queries)} rag query(ies), "
            f"{len(research.urls_to_scrape)} URL(s), "
            f"{len(research.workspace_reads)} workspace path(s)"
        )
        event = self._event("researcher", summary, research.model_dump())
        self.state_store.add_event(state["run_id"], "researcher", event)
        return {"research_plan": research.model_dump(), "trace": [event]}

    async def _executor_node(self, state: AgentState) -> dict[str, Any]:
        plan = await self.ollama.structured_invoke(
            state["selected_model"],
            ExecutorPlan,
            executor_system_prompt(),
            executor_user_prompt(state, self.settings.max_actions_per_iteration),
        )

        gathered: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []

        for action in plan.actions[: self.settings.max_actions_per_iteration]:
            result_items = await self._run_action(action.tool, action.input)
            for item in result_items:
                gathered.append(item)
            summary = f"{action.tool} → {len(result_items)} item(s)"
            event = self._event("executor", summary, {"tool": action.tool, "input": action.input})
            trace.append(event)
            self.state_store.add_event(state["run_id"], "executor", event)

        completion = self._event(
            "executor",
            f"{len(plan.actions[: self.settings.max_actions_per_iteration])} action(s) executed",
            plan.model_dump(),
        )
        trace.append(completion)
        self.state_store.add_event(state["run_id"], "executor", completion)

        return {"gathered_context": gathered[: self.settings.max_evidence_items], "trace": trace}

    async def _critic_node(self, state: AgentState) -> dict[str, Any]:
        critique = await self.ollama.structured_invoke(
            state["selected_model"],
            CriticReview,
            critic_system_prompt(),
            critic_user_prompt(state),
        )
        next_iteration = int(state.get("iteration", 0)) + 1
        done = critique.status in {"done", "failed"} or next_iteration >= int(state.get("max_iterations", 1))
        stop_reason = critique.status
        final_answer = critique.final_answer.strip()
        
        evidence_count = len(state.get("gathered_context", []))
        if critique.status == "continue" and evidence_count == 0 and next_iteration >= 2:
            done = True
            stop_reason = "no_evidence"

        if done and not final_answer:
            final_answer = await self._compose_fallback_answer(state)

        if next_iteration >= int(state.get("max_iterations", 1)) and critique.status == "continue":
            done = True
            stop_reason = "max_iterations"

        event = self._event("critic", critique.reasoning, critique.model_dump())
        self.state_store.add_event(state["run_id"], "critic", event)
        return {
            "critic": critique.model_dump(),
            "iteration": next_iteration,
            "done": done,
            "final_answer": final_answer,
            "stop_reason": stop_reason,
            "trace": [event],
        }

    async def _compose_fallback_answer(self, state: dict[str, Any]) -> str:
        return await self.ollama.plain_invoke(
            state["selected_model"],
            fallback_answer_system_prompt(),
            fallback_answer_user_prompt(state),
        )

    async def _run_action(self, tool_name: str, tool_input: dict[str, Any]) -> list[dict[str, Any]]:
        if tool_name == "web_search":
            logger.info("web_search action input", extra={"tool_input": tool_input})

            query = ""
            if isinstance(tool_input, str):
                query = tool_input.strip()
            elif isinstance(tool_input, dict):
                query = str(
                    tool_input.get("query")
                    or tool_input.get("q")
                    or tool_input.get("search")
                    or ""
                ).strip()

            logger.info("web_search parsed query", extra={"query": query})

            if not query:
                logger.warning("web_search skipped because query is empty", extra={"tool_input": tool_input})
                return []

            results = await self.websearch.search(query, k=self.settings.max_web_results)
            logger.info("web_search returned results", extra={"query": query, "count": len(results)})

            items: list[dict[str, Any]] = []
            for idx, result in enumerate(results, start=1):
                items.append(
                    {
                        "ref": f"web-{uuid.uuid4().hex[:8]}",
                        "tool": "web_search",
                        "title": result.get("title", ""),
                        "source": result.get("url", ""),
                        "content": result.get("content", ""),
                        "meta": {"rank": idx, "engine": result.get("engine", "")},
                    }
                )
            return items

        if tool_name == "scrape_url":
            url = str(tool_input.get("url", "")).strip()
            if not url:
                return []
            result = await self.scraper.fetch(url)
            return [
                {
                    "ref": f"scrape-{uuid.uuid4().hex[:8]}",
                    "tool": "scrape_url",
                    "title": result.get("title", ""),
                    "source": result.get("url", url),
                    "content": result.get("content", ""),
                    "meta": {"content_type": result.get("content_type", "")},
                }
            ]

        if tool_name == "rag_search":
            query = ""
            if isinstance(tool_input, str):
                query = tool_input.strip()
            elif isinstance(tool_input, dict):
                query = str(
                    tool_input.get("query")
                    or tool_input.get("q")
                    or tool_input.get("search")
                    or ""
                ).strip()

            if not query:
                return []

            result = self.rag.search(query, k=self.settings.max_rag_results)
            items: list[dict[str, Any]] = []
            for hit in result.get("results", []):
                items.append(
                    {
                        "ref": f"rag-{uuid.uuid4().hex[:8]}",
                        "tool": "rag_search",
                        "title": hit.get("source", ""),
                        "source": hit.get("source", ""),
                        "content": hit.get("text", ""),
                        "meta": {"score": hit.get("score", 0.0), "chunk_index": hit.get("chunk_index")},
                    }
                )
            return items

        if tool_name == "workspace_list":
            relative_path = str(tool_input.get("path", "."))
            items = self.workspace.list_files(relative_path)
            content = "\n".join(f"{item['type']}: {item['path']}" for item in items)
            return [
                {
                    "ref": f"workspace-{uuid.uuid4().hex[:8]}",
                    "tool": "workspace_list",
                    "title": relative_path,
                    "source": relative_path,
                    "content": content,
                    "meta": {},
                }
            ]

        if tool_name == "workspace_read":
            relative_path = str(tool_input.get("path", "")).strip()
            if not relative_path:
                return []
            item = self.workspace.read_file(relative_path)
            return [
                {
                    "ref": f"workspace-{uuid.uuid4().hex[:8]}",
                    "tool": "workspace_read",
                    "title": item.get("path", relative_path),
                    "source": item.get("path", relative_path),
                    "content": item.get("content", ""),
                    "meta": {},
                }
            ]

        return []

    @staticmethod
    def _extract_goal(messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"])
        return "No explicit user goal provided."

    @staticmethod
    def _event(node: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "node": node,
            "summary": summary,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _chunk_text(text: str, size: int = 80) -> list[str]:
        return [text[i : i + size] for i in range(0, len(text), size)]