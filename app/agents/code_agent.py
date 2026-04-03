import os
import logging
from langchain_groq import ChatGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------
# LLM SETUP
# Low temperature for deterministic code output
# -----------------------------------------------
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.1,
)


async def run_code_agent(task: str) -> dict:
    logger.info(f"Code Agent running. Task: {task}")

    # -----------------------------------------------
    # CODE AGENT PROMPT
    # Generates clean, documented, production-ready code
    # Temperature is set to 0.1 for consistent output
    # -----------------------------------------------
    code_prompt = f"""
    You are an expert software developer assistant.
    Your goal is to write clean, production-ready code based on the user's request.
    
    RULES:
    - Write working, clean and readable code
    - Add a brief explanation before the code
    - Use ``` code blocks
    - Include usage examples where appropriate
    - Add error handling (try/except or equivalent)
    - Follow best practices and design patterns
    - Use meaningful variable and function names
    - Add inline comments for complex logic
    - Respond with explanation in Turkish, code can be in English
    
    USER REQUEST:
    {task}
    
    Write the code and briefly explain what it does.
    """

    response = await llm.ainvoke(code_prompt)

    return {
        "response_type": "code",
        "message": response.content,
        "references": [],
        "redirected_to": None,
    }