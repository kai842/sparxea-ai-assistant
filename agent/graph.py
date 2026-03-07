from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from agent.config import get_llm
from agent.tools import (
    search_model,
    get_element_details,
    get_package_contents,
    run_sql_query,
    create_element_in_model,
    update_element_notes_in_model,
    set_tagged_value_in_model,
    create_connector_in_model,
)

TOOLS = [
    search_model,
    get_element_details,
    get_package_contents,
    run_sql_query,
    create_element_in_model,
    update_element_notes_in_model,
    set_tagged_value_in_model,
    create_connector_in_model,
]

SYSTEM_PROMPT = SystemMessage(content="""
You are an AI assistant for Sparx Enterprise Architect (EA).
You help users analyze, understand, and modify their architecture models.

Read tools:
- search_model:              semantic + keyword search over all model elements
- get_element_details:       full details for a specific element by name
- get_package_contents:      list all elements inside a package
- run_sql_query:             execute a SQL SELECT on the EA database

Write tools (require user confirmation):
- create_element_in_model:           create a new element
- update_element_notes_in_model:     update element description
- set_tagged_value_in_model:         set or update a Tagged Value
- create_connector_in_model:         create a relationship between elements

Important instructions:
- Always use search_model first to find relevant elements.
- For ALL write operations: first call the tool with confirmed=False to show
  the planned action, then wait for the user to confirm with 'yes' before
  calling again with confirmed=True.
- When calling a write tool with confirmed=True, you MUST use exactly the
  same parameter values (name, package_name, ea_type, stereotype) as shown
  in the confirmation message. Never change any parameters between the
  preview call and the confirmed call.
- Never expose internal tokens (ELEMENT_001) in your answers.
- After any write action, remind the user to click 'Update Data' in the UI
  to refresh the vector database.
- Always answer in English, regardless of the language the user writes in.
- Be concise and precise.
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