"""
LangGraph interview state machine graph definition.
Explicit node connections with conditional routing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, END

from app.graph.state import InterviewState
from app.graph.nodes import (
    node_load_plan,
    node_select_question,
    node_present_question,
    node_evaluate_answer,
    node_decide_next,
    node_generate_report,
)

logger = logging.getLogger(__name__)


def route_after_load(state: InterviewState) -> Literal["select_question", "__end__"]:
    if state.get("status") == "abandoned":
        return END
    return "select_question"


def route_after_select(state: InterviewState) -> Literal["present_question", "generate_report"]:
    if state.get("status") == "completed" or state.get("current_question") is None:
        return "generate_report"
    return "present_question"


def route_after_decide(state: InterviewState) -> Literal["present_question", "select_question", "generate_report"]:
    action = state.get("last_action", "")
    status = state.get("status", "")

    if status == "completed" or action == "end_interview":
        return "generate_report"
    elif action == "follow_up":
        # A follow-up question was set; go directly to present
        return "present_question"
    else:
        return "select_question"


def build_interview_graph() -> StateGraph:
    """
    Build and compile the LangGraph interview workflow.

    Graph:
    START → load_plan → select_question → present_question
         → [suspend for answer] → evaluate_answer → decide_next
         → (follow_up → present_question) | (next → select_question) | (end → generate_report)
         → END
    """
    workflow = StateGraph(InterviewState)

    # Add nodes
    workflow.add_node("load_plan", node_load_plan)
    workflow.add_node("select_question", node_select_question)
    workflow.add_node("present_question", node_present_question)
    workflow.add_node("evaluate_answer", node_evaluate_answer)
    workflow.add_node("decide_next", node_decide_next)
    workflow.add_node("generate_report", node_generate_report)

    # Entry point
    workflow.set_entry_point("load_plan")

    # Edges
    workflow.add_conditional_edges("load_plan", route_after_load)
    workflow.add_conditional_edges("select_question", route_after_select)
    workflow.add_edge("present_question", END)           # Suspend here — answer arrives via API
    workflow.add_edge("evaluate_answer", "decide_next")
    workflow.add_conditional_edges("decide_next", route_after_decide)
    workflow.add_edge("generate_report", END)

    return workflow.compile()


# Singleton graph instance
_graph = None


def get_interview_graph():
    global _graph
    if _graph is None:
        _graph = build_interview_graph()
    return _graph


async def run_graph_until_suspend(
    state: Dict[str, Any],
    start_from_node: str = "load_plan",
) -> Dict[str, Any]:
    """
    Run the graph from the given node until it suspends (awaiting_answer=True)
    or completes. Returns the updated state.
    """
    graph = get_interview_graph()
    try:
        result = await graph.ainvoke(state)
        return result
    except Exception as e:
        logger.error(f"Graph execution error: {e}")
        return {**state, "status": "active", "error_message": str(e)}


async def resume_graph_with_answer(
    state: Dict[str, Any],
    answer_text: str,
    skipped: bool = False,
) -> Dict[str, Any]:
    """
    Resume the graph after the candidate submits an answer.
    Injects the answer into state and runs from evaluate_answer.
    """
    updated_state = {
        **state,
        "current_answer": answer_text,
        "current_answer_skipped": skipped,
        "awaiting_answer": False,
    }

    graph = get_interview_graph()
    try:
        # We need to run from evaluate_answer node
        # Create a minimal graph that starts at evaluate_answer
        resume_workflow = StateGraph(InterviewState)
        resume_workflow.add_node("evaluate_answer", node_evaluate_answer)
        resume_workflow.add_node("decide_next", node_decide_next)
        resume_workflow.add_node("select_question", node_select_question)
        resume_workflow.add_node("present_question", node_present_question)
        resume_workflow.add_node("generate_report", node_generate_report)

        resume_workflow.set_entry_point("evaluate_answer")
        resume_workflow.add_edge("evaluate_answer", "decide_next")
        resume_workflow.add_conditional_edges("decide_next", route_after_decide)
        resume_workflow.add_conditional_edges("select_question", route_after_select)
        resume_workflow.add_edge("present_question", END)
        resume_workflow.add_edge("generate_report", END)

        resume_graph = resume_workflow.compile()
        result = await resume_graph.ainvoke(updated_state)
        return result

    except Exception as e:
        logger.error(f"Graph resume error: {e}")
        return {**updated_state, "error_message": str(e)}
