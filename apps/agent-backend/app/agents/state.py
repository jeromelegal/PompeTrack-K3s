import operator
from typing import Any, Annotated

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: str
    user_id: str | None
    goal: str
    messages: list[dict[str, Any]]
    selected_model: str
    iteration: int
    max_iterations: int
    plan: dict[str, Any]
    research_plan: dict[str, Any]
    critic: dict[str, Any]
    gathered_context: Annotated[list[dict[str, Any]], operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
    done: bool
    final_answer: str
    stop_reason: str
