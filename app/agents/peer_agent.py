import os
import logging
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from app.core.config import settings

logger = logging.getLogger(__name__)

os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

search_tool = TavilySearch(max_results=3)


async def run_peer_agent(task: str, has_problem_tree: bool = False) -> dict:
    logger.info(f"Peer Agent running. Task: {task}")

    if has_problem_tree:
        category_prompt = f"""
        The user has a previously generated problem tree.
        
        RULE: If the question is related to business or strategy and could be connected to the problem tree, ALWAYS select ANALYSIS!
        
        Only select a category other than ANALYSIS in these cases:
        - Defining a completely new and different business problem → REDIRECT
        - Greeting or farewell → GREETING
        - Completely non-business topic like food, music, movies → OUT_OF_SCOPE
        
        All other business questions → ANALYSIS
        
        Task: {task}
        Write only the category name.
        """
    else:
        category_prompt = f"""
        Analyze the following request and write only the category name:
        - DIRECT_ANSWER: Business knowledge question (competition, market, sector trends)
        - REDIRECT: Business problem (sales decline, cost increase, operational issue)
        - CODE: Code writing, scripting, algorithm or software development request
        - OUT_OF_SCOPE: Non-business and non-code request (recipes, entertainment, daily life)
        - GREETING: Greeting, thank you, farewell or general conversation
        
        Task: {task}
        
        Write only the category name, nothing else.
        """

    category_response = await llm.ainvoke(category_prompt)
    category = category_response.content.strip().upper()

    logger.info(f"Peer Agent category: {category}")

    if "DIRECT_ANSWER" in category:
        search_results = search_tool.invoke(task)
        logger.info(f"Search results raw: {type(search_results)}")
        
        # Tavily farklı formatlarda dönebilir
        if isinstance(search_results, dict):
            results_list = search_results.get("results", [])
        elif isinstance(search_results, list):
            results_list = search_results
        else:
            results_list = []
        
        references = [r.get("url", "") for r in results_list if isinstance(r, dict)]
        content = "\n".join([r.get("content", "") for r in results_list if isinstance(r, dict)])
        logger.info(f"References found: {len(references)}")

        answer_prompt = f"""
        You are a professional business analyst assistant.
        
        The user asked: {task}
        
        Information found on the web:
        {content}
        
        Provide a short, clear and structured business answer.
        - Use bullet points or numbered lists where appropriate
        - Include key insights and trends
        - Respond in Turkish language
        """
        answer = await llm.ainvoke(answer_prompt)

        return {
            "response_type": "direct_answer",
            "message": answer.content,
            "references": references,
            "redirected_to": None,
        }

    elif "REDIRECT" in category:
        return {
            "response_type": "redirect",
            "message": "Talebiniz bir business problemi analizi gerektiriyor. Sizi Business Sense Discovery Agent'a yönlendiriyorum. Problem keşif süreci başlayacak.",
            "references": [],
            "redirected_to": "discovery_agent",
        }

    elif "CODE" in category:
        return {
            "response_type": "code",
            "message": "",
            "references": [],
            "redirected_to": "code_agent",
        }

    elif "GREETING" in category:
        greeting_prompt = f"""
        You are a professional business assistant.
        The user said: {task}
        
        This is a greeting, thank you, or farewell message.
        Respond naturally and warmly.
        - Do NOT start with "Merhaba" if the user said thank you
        - Keep it short and professional
        - If appropriate, invite them to ask another business question
        - Respond in Turkish language
        """
        greeting_response = await llm.ainvoke(greeting_prompt)
        return {
            "response_type": "greeting",
            "message": greeting_response.content,
            "references": [],
            "redirected_to": None,
        }

    elif "ANALYSIS" in category:
        return {
            "response_type": "analysis",
            "message": "",
            "references": [],
            "redirected_to": "analysis_agent",
        }

    else:
        out_of_scope_prompt = f"""
        You are a professional business assistant.
        The user requested: {task}
        
        This system is designed only for business and strategy problems.
        - Politely explain that this is outside the system's scope
        - Offer 2-3 example questions that reframe the same topic from a business perspective
        - Respond in Turkish language
        """
        response = await llm.ainvoke(out_of_scope_prompt)

        return {
            "response_type": "out_of_scope",
            "message": response.content,
            "references": [],
            "redirected_to": None,
        }