import os
import subprocess
from dotenv import load_dotenv
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
import re

from prompt import system_prompt

# Load API Key
load_dotenv('.env')
openai_api_key = os.getenv('OPENAI_API_KEY')

# Define state schema
class WorkflowState(TypedDict):
    query: str
    action: str
    result: str

# Initialize LLM
def get_LLM():
    return ChatOpenAI(model_name="gpt-3.5-turbo", openai_api_key=openai_api_key)

# Function to create a project directory
def create_project_directory(project_name: str):
    project_name = clean_name(project_name)
    os.makedirs(project_name, exist_ok=True)
    return f"Project directory '{project_name}' created."

# Function to create a file inside a project directory
def create_file(project_name: str, filename: str = None, content: str = ""):
    if not filename:
        return "Error: Filename is required to create a file."

    project_name = clean_name(project_name)
    filename = clean_name(filename)

    os.makedirs(project_name, exist_ok=True)  # Ensure the directory exists

    with open(os.path.join(project_name, filename), 'w') as f:
        f.write(content)

    return f"File '{filename}' created in '{project_name}'."

# Function to install dependencies from requirements.txt
def install_dependencies():
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'])
    return "Dependencies installed."

# Function to clean invalid characters from names
def clean_name(name: str):
    return re.sub(r'[<>:"/\\|?*]', '_', name.strip())

# Define LangChain tools for the AI Agent
tools = [
    Tool(name="Create Directory", func=create_project_directory, description="Creates a project directory."),
    Tool(
            name="Create File",
            func=lambda project_name, filename, content="": create_file(project_name, filename, content),
            description="Creates a file inside a project directory. Usage: Create File with 'project_name', 'filename', and optional 'content'."
        ),    
    Tool(name="Install Dependencies", func=install_dependencies, description="Installs required dependencies from a requirements.txt file."),
]

# Initialize LangChain Agent
def get_agent():
    return initialize_agent(tools=tools, llm=get_LLM(), agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Detect if user input is general or an action request
def is_general_query(query: str):
    general_keywords = ["hello", "hi", "how are you", "what's up", "help", "who are you"]
    return any(word in query.lower() for word in general_keywords)

# Process user query using LangChain Agent or return a general response
def process_query(state: WorkflowState) -> WorkflowState:
    query = state["query"]

    if is_general_query(query):
        return {"query": query, "action": "general_response", "result": general_response(query)}

    agent = get_agent()
    action_result = agent.run(query)

    action_result = extract_parameters(action_result)

    return {"query": query, "action": action_result, "result": ""}

# Function to generate a response for general queries
def general_response(query: str):
    responses = {
        "hello": "Hello! How can I assist you today?",
        "hi": "Hi there! Need help with a project?",
        "how are you": "I'm an AI assistant, always ready to help! What do you need?",
        "what's up": "Just here to help you with your projects! What do you need?",
        "help": "I can assist with setting up coding projects. Try asking: 'Create a Python project named MyApp'.",
        "who are you": "I'm an AI assistant designed to help you with software development and project setup."
    }
    
    for key in responses:
        if key in query.lower():
            return responses[key]

    return "I'm here to help with coding projects. What do you need?"

# Function to extract clean parameters from agent output
def extract_parameters(action_result: str):
    match = re.search(r'create project\s* \s*["\']?([^"\']+)["\']?', action_result)
    if match:
        action_result = match.group(1)
    return action_result

# Execute the function based on AI agent's decision
def execute_action(state: WorkflowState) -> WorkflowState:
    if state["action"] == "general_response":
        return {"query": state["query"], "action": "general_response", "result": state["result"]}

    return {"query": state["query"], "action": state["action"], "result": state["action"]}

# Define LangGraph workflow
def build_graph():
    workflow = StateGraph(WorkflowState)

    workflow.add_node("process_query", RunnableLambda(process_query))
    workflow.add_node("execute_action", RunnableLambda(execute_action))

    workflow.set_entry_point("process_query")
    workflow.add_edge("process_query", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()

# Interactive Chatbot
def main():
    print("Welcome to AI Project Setup Assistant! Type 'exit' to quit.")
    workflow = build_graph()

    while True:
        query = input("Type something: ")
        if query.lower() == 'exit':
            print("Goodbye!")
            break

        state = {"query": query, "action": "", "result": ""}
        result = workflow.invoke(state)
        print(result["result"])

if __name__ == "__main__":
    main()
