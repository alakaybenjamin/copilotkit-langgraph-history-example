"""
LangGraph Agent Definition

A simple ReAct-style agent with:
- Weather tool (example)
- PostgreSQL checkpoint persistence
- CopilotKit state integration
"""

import os
from typing import Literal

from copilotkit import CopilotKitState
from langchain.tools import tool
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command


class AgentState(CopilotKitState):
    """
    Agent state extending CopilotKitState.
    
    CopilotKitState provides:
    - messages: List of conversation messages
    - copilotkit: Dict with actions (frontend tools) and context
    """
    # Add any custom state fields here
    conversation_summary: str = ""


@tool
def get_weather(location: str) -> str:
    """
    Get the current weather for a location.
    
    Args:
        location: The city or location to get weather for
    
    Returns:
        Weather information for the location
    """
    # Mock weather data - in production, call a real weather API
    weather_data = {
        "new york": "Sunny, 72°F (22°C)",
        "london": "Cloudy, 59°F (15°C)",
        "tokyo": "Rainy, 68°F (20°C)",
        "paris": "Partly cloudy, 65°F (18°C)",
        "sydney": "Clear, 77°F (25°C)",
    }
    
    location_lower = location.lower()
    for city, weather in weather_data.items():
        if city in location_lower:
            return f"The weather in {location} is: {weather}"
    
    return f"Weather data not available for {location}. Try: New York, London, Tokyo, Paris, or Sydney."


@tool
def get_time(timezone: str = "UTC") -> str:
    """
    Get the current time in a timezone.
    
    Args:
        timezone: The timezone (e.g., "UTC", "EST", "PST")
    
    Returns:
        Current time in the specified timezone
    """
    from datetime import datetime, timezone as tz
    
    now = datetime.now(tz.utc)
    return f"The current time in {timezone} is approximately {now.strftime('%I:%M %p')} UTC"


# Define available tools
tools = [get_weather, get_time]


def should_route_to_tool_node(tool_calls, fe_tools) -> bool:
    """
    Determine if we should route to the tool node.
    
    Returns True if the tool calls are backend tools (not frontend actions).
    """
    if not tool_calls:
        return False
    
    fe_tool_names = {tool.get("name") for tool in (fe_tools or [])}
    
    for tool_call in tool_calls:
        tool_name = (
            tool_call.get("name")
            if isinstance(tool_call, dict)
            else getattr(tool_call, "name", None)
        )
        if tool_name in fe_tool_names:
            return False
    
    return True


async def chat_node(
    state: AgentState, 
    config: RunnableConfig
) -> Command[Literal["tool_node", "__end__"]]:
    """
    Main chat node using the ReAct pattern.
    
    1. Gets frontend tools from CopilotKit state
    2. Binds all tools to the model
    3. Generates a response
    4. Routes to tool_node or ends
    """
    # Initialize the model
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    
    # Get frontend tools from CopilotKit state
    fe_tools = state.get("copilotkit", {}).get("actions", [])
    
    # Bind all tools to the model
    model_with_tools = model.bind_tools([*fe_tools, *tools])
    
    # Create system message
    system_message = SystemMessage(
        content="""You are a helpful assistant with access to tools.
        
You can:
- Check the weather in various cities
- Tell the current time

Be friendly and conversational. If the user asks about something you can't help with,
let them know politely.

Remember: You have persistent memory! Previous conversations in this thread are preserved."""
    )
    
    # Generate response
    response = await model_with_tools.ainvoke(
        [system_message, *state["messages"]],
        config,
    )
    
    # Check if we need to call tools
    tool_calls = response.tool_calls
    if tool_calls and should_route_to_tool_node(tool_calls, fe_tools):
        return Command(goto="tool_node", update={"messages": response})
    
    # No tool calls - end the conversation turn
    return Command(goto="__end__", update={"messages": response})


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow (without compiling).
    
    Returns:
        Uncompiled StateGraph
    """
    # Build the workflow
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tool_node", ToolNode(tools=tools))
    
    # Add edges
    workflow.add_edge("tool_node", "chat_node")
    workflow.set_entry_point("chat_node")
    
    return workflow
