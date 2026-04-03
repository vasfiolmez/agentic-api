import os
import logging
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------
# LLM AND SEARCH TOOL SETUP
# -----------------------------------------------
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

search_tool = TavilySearch(max_results=3)


async def run_analysis_agent(task: str, problem_tree: dict) -> dict:
    logger.info(f"Analysis Agent running. Task: {task}")

    # -----------------------------------------------
    # FORMAT PROBLEM TREE
    # Convert dict to readable text for LLM context
    # -----------------------------------------------
    problem_tree_text = ""
    if problem_tree:
        problem_type = problem_tree.get("problem_type", "")
        main_problem = problem_tree.get("main_problem", "")
        problem_tree_text = f"Problem Type: {problem_type}\n"
        problem_tree_text += f"Main Problem: {main_problem}\n\n"
        problem_tree_text += "Problem Tree:\n"

        for node in problem_tree.get("problem_tree", []):
            root_cause = node.get("root_cause", "")
            problem_tree_text += f"\n• {root_cause}\n"
            for sub_cause in node.get("sub_causes", []):
                problem_tree_text += f"  - {sub_cause}\n"

    # -----------------------------------------------
    # GET ADDITIONAL WEB INFORMATION
    # -----------------------------------------------
    search_results = search_tool.invoke(task)
    if isinstance(search_results, dict):
        results_list = search_results.get("results", [])
    elif isinstance(search_results, list):
        results_list = search_results
    else:
        results_list = []

    web_content = "\n".join([r.get("content", "") for r in results_list if isinstance(r, dict)])

    # -----------------------------------------------
    # ANALYSIS AGENT PROMPT
    # Uses problem tree as context to answer questions
    # -----------------------------------------------
    analysis_prompt = f"""
    You are a Problem Analysis Agent.
    Your goal is to analyze the customer's previously generated problem tree
    and provide deep insights and answers to their questions.
    
    RULES:
    - Use the problem tree as your primary context
    - Enrich your answer with web information if relevant
    - Provide a short, clear and structured response
    - Do NOT start new problem discovery
    - Reference specific root causes and sub-causes from the problem tree
    - Respond in Turkish language
    
    PROBLEM TREE CONTEXT:
    {problem_tree_text}
    
    ADDITIONAL WEB INFORMATION:
    {web_content}
    
    CUSTOMER QUESTION:
    {task}
    
    Answer the question in the context of the problem tree.
    Use bullet points and bold text for clarity.
    """

    response = await llm.ainvoke(analysis_prompt)

    return {
        "response_type": "analysis",
        "message": response.content,
        "references": [r.get("url", "") for r in search_results if isinstance(r, dict)],
    }