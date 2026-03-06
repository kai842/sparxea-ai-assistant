from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from agent.config import get_llm
from agent.tools import (
    get_all_elements,
    get_element_details,
    get_connectors_for_element,
    get_package_contents,
    run_sql_query,
)

TOOLS = [
    get_all_elements,
    get_element_details,
    get_connectors_for_element,
    get_package_contents,
    run_sql_query,
]

SYSTEM_PROMPT = SystemMessage(content="""
You are an AI assistant for Sparx Enterprise Architect (EA).
You help users analyze and understand their architecture models.

Important instructions:
- Element identifiers like ELEMENT_001 are internal tokens.
  Always refer to elements by their resolved real name, never as 'token'.
- Be concise and precise in your answers.
- When listing elements, use their name and type only.
""")


class AgentState(TypedDict):
    """
    Carries the full conversation history and tool results
    across all nodes in the LangGraph ReAct cycle.
    """
    messages: Annotated[list, add_messages]


def build_graph():
    """Builds and compiles the ReAct agent graph."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    def call_llm(state: AgentState):
        """Node: sends messages to the LLM and returns its response."""
        messages = [SYSTEM_PROMPT] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState):
        """Edge: routes to tools if LLM requested a tool call, else ends."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "llm")

    return graph.compile()
