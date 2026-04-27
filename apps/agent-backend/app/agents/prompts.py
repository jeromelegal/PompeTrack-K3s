from __future__ import annotations

import json
from typing import Any


def render_messages(messages: list[dict[str, Any]], limit: int = 12) -> str:
    tail = messages[-limit:]
    lines: list[str] = []
    for message in tail:
        role = str(message.get("role", "unknown")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def render_evidence(evidence: list[dict[str, Any]], limit: int = 10) -> str:
    lines: list[str] = []
    for item in evidence[-limit:]:
        ref = item.get("ref", "unknown")
        source = item.get("source", "")
        title = item.get("title", "")
        content = item.get("content", "")
        tool = item.get("tool", "")
        lines.append(
            f"[{ref}] tool={tool} title={title} source={source}\n"
            f"{content[:1500]}"
        )
    return "\n\n".join(lines) if lines else "No evidence yet."


def planner_system_prompt() -> str:
    return (
        "You are the PLANNER in a local multi-agent system. "
        "Decompose the user's goal into a short, practical plan. "
        "Stay concise, realistic, and grounded in the available tools. "
        "Reply strictly with JSON matching the schema. "
        "Keep the answer language aligned with the user's language."
    )


def planner_user_prompt(state: dict[str, Any]) -> str:
    return f"""
Current iteration: {state.get("iteration", 0)} / {state.get("max_iterations", 0)}
User goal:
{state.get("goal", "")}

Recent conversation:
{render_messages(state.get("messages", []))}

Previous plan:
{json.dumps(state.get("plan", {}), ensure_ascii=False, indent=2)}

Current evidence:
{render_evidence(state.get("gathered_context", []), limit=6)}

Critic feedback:
{json.dumps(state.get("critic", {}), ensure_ascii=False, indent=2)}
""".strip()


def researcher_system_prompt() -> str:
    return (
        "You are the RESEARCHER in a local multi-agent system. "
        "Choose the minimum useful evidence-gathering steps. "
        "Available capabilities: web_search, scrape_url, rag_search, workspace_read. "
        "Do not invent URLs. Prefer short query lists. "
        "Return plain query strings, not tool call JSON. "
        "Reply strictly with JSON matching the schema."
    )


def researcher_user_prompt(state: dict[str, Any]) -> str:
    return f"""
User goal:
{state.get("goal", "")}

Conversation:
{render_messages(state.get("messages", []))}

Current plan:
{json.dumps(state.get("plan", {}), ensure_ascii=False, indent=2)}

Known evidence:
{render_evidence(state.get("gathered_context", []), limit=8)}

Critic feedback:
{json.dumps(state.get("critic", {}), ensure_ascii=False, indent=2)}
""".strip()


def executor_system_prompt() -> str:
    return (
        "You are the EXECUTOR in a local multi-agent system. "
        "Transform the research plan into a small set of safe tool actions. "
        "Allowed tools: web_search, scrape_url, rag_search, workspace_list, workspace_read. "
        "Never request shell, code execution, or dangerous actions. "
        "VERY IMPORTANT: never emit an action with empty input {}. "
        "For web_search and rag_search, input MUST be {'query': '<non-empty string>'}. "
        "For scrape_url, input MUST be {'url': '<non-empty url>'}. "
        "For workspace_read and workspace_list, input MUST be {'path': '<non-empty path>'}. "
        "Convert each research_plan item directly into the matching tool action. "
        "If there is no valid action to execute, return actions=[] instead of invalid actions. "
        "Reply strictly with JSON matching the schema."
    )


def executor_user_prompt(state: dict[str, Any], max_actions: int) -> str:
    return f"""
User goal:
{state.get("goal", "")}

Current plan:
{json.dumps(state.get("plan", {}), ensure_ascii=False, indent=2)}

Research plan:
{json.dumps(state.get("research_plan", {}), ensure_ascii=False, indent=2)}

Evidence already available:
{render_evidence(state.get("gathered_context", []), limit=8)}

Maximum actions allowed in this iteration: {max_actions}

Rules for action formatting:
- Each web_queries item becomes: {{"tool": "web_search", "input": {{"query": "..."}}}}
- Each rag_queries item becomes: {{"tool": "rag_search", "input": {{"query": "..."}}}}
- Each urls_to_scrape item becomes: {{"tool": "scrape_url", "input": {{"url": "..."}}}}
- Each workspace_reads item becomes: {{"tool": "workspace_read", "input": {{"path": "..."}}}}
- Never output input={{}}.
- Never invent URLs or file paths.
- Prefer the smallest useful set of actions.
""".strip()


def critic_system_prompt() -> str:
    return (
        "You are the CRITIC in a local multi-agent system. "
        "Judge whether the system has enough evidence to answer. "
        "Prefer finishing when the answer is already good enough. "
        "If you can answer, produce a final answer grounded in the evidence and cite evidence refs like [web-1] or [rag-2]. "
        "If evidence is insufficient, return status='continue' with concrete missing_info. "
        "If there is still no evidence after at least one full research/execution cycle, do NOT keep looping repeatedly. "
        "In that case, prefer status='done' with a useful fallback answer that clearly states external search was insufficient or unavailable. "
        "Reply strictly with JSON matching the schema."
    )


def critic_user_prompt(state: dict[str, Any]) -> str:
    return f"""
User goal:
{state.get("goal", "")}

Conversation:
{render_messages(state.get("messages", []))}

Plan:
{json.dumps(state.get("plan", {}), ensure_ascii=False, indent=2)}

Evidence:
{render_evidence(state.get("gathered_context", []), limit=12)}

Current iteration: {state.get("iteration", 0)} / {state.get("max_iterations", 0)}
""".strip()


def fallback_answer_system_prompt() -> str:
    return (
        "You are the final answer composer for a local multi-agent system. "
        "Write a clear answer for the user using the supplied evidence when available. "
        "If evidence is empty or too weak, you may provide a best-effort answer from general model knowledge, "
        "but you MUST explicitly say that external evidence could not be collected or was insufficient. "
        "Cite evidence refs inline when relevant. "
        "State uncertainty explicitly when evidence is missing. "
        "Keep the language aligned with the user's language."
    )


def fallback_answer_user_prompt(state: dict[str, Any]) -> str:
    return f"""
User goal:
{state.get("goal", "")}

Conversation:
{render_messages(state.get("messages", []))}

Plan:
{json.dumps(state.get("plan", {}), ensure_ascii=False, indent=2)}

Evidence:
{render_evidence(state.get("gathered_context", []), limit=12)}
""".strip()