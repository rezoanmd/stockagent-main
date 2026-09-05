import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

# import langchain.chat_models as cm

from langchain.chat_models import init_chat_model

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.0)

# defining the agent state

from typing_extensions import TypedDict, List

class State(TypedDict):
    question: str
    answer: str
    history: List[str]

# defining the node functions for workflow

def classify(state: State) -> str:

    # this is a function where we use to classify the questions into a category
    # and manage routing of the question to the right agent

    # for now, this is just a placeholder function

    return {"question": state["question"]}

def generate(state: State) -> str:

    # this is a function where we use to generate the answer to the question
    # using the llm

    context = "\n".join(state.get("history", []))

    prompt = f"""

    You are a conversational AI Assistant. Use the context history to reply naturally, and keep everything concise.

    context:    {context}

    question:   {state["question"]}

    """

    response = llm.invoke([{
        "role" : "user",
        "content" : prompt,
        }])
    
    return {"answer" : response.content}

def refine(state):

    # this is just a placeholder refinement for now, we might shorten answers/improve grammar/format or anything here.
    
    refined = state["answer"] + "\n\n [refined for clarity]"

    history = state.get("history", [])

    history.append(f"Q: {state["question"]} \nA: {refined}")

    return {"answer" : refined, "history" : history}

# building LangGraph Workflow

from langgraph.graph import START, StateGraph

graph_builder = StateGraph(State).add_sequence([classify, generate, refine])
graph_builder.add_edge(START, "classify")

graph = graph_builder.compile()


state = {
    "question" : "",
    "answer" : "",
    "history" : [],
}

print("AI Agent with memory is ready! Type 'exit' to quit.\n")

while True:

    question = input("Ask a question: ")

    if question.lower() in ("exit", "quit"):
        break

    state["question"] = question
    response = graph.invoke(state)
    state.update(response)

    print("\nAnswer:\n", response.get("answer", "answer is not generated"))
    print("\n" + "=" * 60 + "\n")