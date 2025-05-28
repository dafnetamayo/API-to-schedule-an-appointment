# caller_agent.py

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, MessagesState
import datetime
from tools import (
    get_next_available_appointment,
    get_all_available_appointments,
    book_appointment_by_slot,
    cancel_appointment
)
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4o")

# Conversation history
CONVERSATION = []

def receive_message_from_caller(message: str):
    """
    Append the user's message to the conversation and
    drive the state graph to produce a response.
    """
    CONVERSATION.append(HumanMessage(content=message, type="human"))
    state = {"messages": CONVERSATION}
    new_state = caller_app.invoke(state)
    CONVERSATION.extend(new_state["messages"][len(CONVERSATION):])

def should_continue_caller(state: MessagesState) -> str:
    """
    If the last message resulted in a tool call, go back to the agent;
    otherwise end the workflow.
    """
    last = state["messages"][-1]
    return "continue" if last.tool_calls else "end"

def call_caller_model(state: MessagesState):
    """
    Inject current time into the prompt context, invoke the LLM,
    and wrap its single output in the expected return format.
    """
    state["current_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    response = caller_model.invoke(state)
    return {"messages": [response]}

# Expose exactly these four tools to the graph:
caller_tools = [
    get_next_available_appointment,
    get_all_available_appointments,
    book_appointment_by_slot,   # <-- the new slot-based booking tool
    cancel_appointment
]

tool_node = ToolNode(caller_tools)

# System prompt: instruct the assistant to use the slot-based booking
caller_pa_prompt = """
You are an extremely polite (almost rude) personal assistant.
You help the user find free 30-minute slots and then book exactly the slot they choose.
Use get_next_available_appointment or get_all_available_appointments to list free times in UTC,
then use book_appointment_by_slot with the exact slot string plus the guest's first and last name.
Current time: {current_time}
"""

caller_chat_template = ChatPromptTemplate.from_messages([
    ("system", caller_pa_prompt),
    ("placeholder", "{messages}")
])

caller_model = caller_chat_template | llm.bind_tools(caller_tools)

# Build the graph
caller_workflow = StateGraph(MessagesState)
caller_workflow.add_node("agent", call_caller_model)
caller_workflow.add_node("action", tool_node)
caller_workflow.add_conditional_edges(
    "agent",
    should_continue_caller,
    {"continue": "action", "end": END}
)
caller_workflow.add_edge("action", "agent")
caller_workflow.set_entry_point("agent")

# Compile the callable app
caller_app = caller_workflow.compile()
