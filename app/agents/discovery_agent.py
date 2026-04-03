import os
import logging
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------
# LLM ve SEARCH TOOL KURULUMU
# Uygulama başladığında bir kez oluşturulur
# -----------------------------------------------
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

search_tool = TavilySearch(max_results=3)


async def run_discovery_agent(task: str, conversation_history: list = []) -> dict:
    logger.info(f"Discovery Agent çalışıyor. Task: {task}")

    # -----------------------------------------------
    # KONUŞMA GEÇMİŞİNİ FORMATLA
    # -----------------------------------------------
    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            role = "Kullanıcı" if msg["role"] == "user" else "Agent"
            history_text += f"{role}: {msg['content']}\n"

    # -----------------------------------------------
    # YETERLİ BİLGİ KONTROLÜ
    # -----------------------------------------------
    if conversation_history and len(conversation_history) >= 6:
        return await _generate_discovery_output(task, conversation_history)

    # -----------------------------------------------
    # SORU ÜRET
    # -----------------------------------------------
    question_prompt = f"""
    ROLE: Expert Business Sense Discovery Agent
    CONTEXT: You are conducting a diagnostic interview with a client to deeply understand their business problem before any solution is offered.
    OBJECTIVE: Ask insightful, probing questions to uncover the true root cause rather than just the surface-level symptoms.

    CONSTRAINTS:
    - NEVER propose solutions or offer advice; your ONLY job right now is to understand the problem.
    - Ask a MAXIMUM of 2 questions per turn.
    - Analyze the "Conversation History" and generate highly relevant follow-up questions based on the client's previous answers.
    - Keep the questions concise, professional, and clear.
    - Output Language: Turkish.

    QUESTIONING FRAMEWORK (Use these themes to guide your questions):
    1. Problem Definition:
       - What is the main problem disrupting your business right now?
       - Which department is directly affected by this issue?
       - When did this problem first appear?
       - How are you currently managing or mitigating this problem?
    2. Real Need vs. Surface Want:
       - Are you looking for an immediate solution, or do you want to understand the root cause first?
       - What solutions have you tried so far, and why did they fail?
       - Do you actually need a new solution, or is there a lack of visibility/data?

    USER'S INITIAL REQUEST: {task}
    
    CONVERSATION HISTORY:
    {history_text if history_text else "No history yet. Ask the initial discovery questions."}

    OUTPUT FORMAT:
    Output ONLY the questions. Do not include introductory text, explanations, markdown blocks, or pleasantries.
    """

    response = await llm.ainvoke(question_prompt)

    return {
        "status": "questioning",
        "message": response.content,
        "is_complete": False,
    }


async def _generate_discovery_output(task: str, conversation_history: list) -> dict:
    logger.info("Discovery Agent çıktı üretiyor...")

    # -----------------------------------------------
    # KONUŞMA GEÇMİŞİNİ FORMATLA
    # -----------------------------------------------
    history_text = ""
    for msg in conversation_history:
        role = "Kullanıcı" if msg["role"] == "user" else "Agent"
        history_text += f"{role}: {msg['content']}\n"

    # -----------------------------------------------
    # WEB'DEN EK BİLGİ AL
    # -----------------------------------------------
    search_results = search_tool.invoke(task)
    if isinstance(search_results, dict):
        results_list = search_results.get("results", [])
    elif isinstance(search_results, list):
        results_list = search_results
    else:
        results_list = []

    web_content = "\n".join([r.get("content", "") for r in results_list if isinstance(r, dict)])

    output_prompt = f"""
    ROLE: Expert Business Diagnostician
    CONTEXT: The diagnostic Q&A phase with the client has concluded.
    OBJECTIVE: Synthesize the entire conversation and supplementary web context into a highly structured diagnostic report.

    USER'S INITIAL REQUEST: {task}

    CONVERSATION HISTORY:
    {history_text}

    SUPPLEMENTARY WEB CONTEXT:
    {web_content}

    CONSTRAINTS:
    - Extract and deduce the necessary information accurately based ONLY on the provided context.
    - Ensure every requested field is populated.
    - Output Language for the content: Turkish.
    - You MUST adhere strictly to the exact keys provided in the OUTPUT FORMAT. Do not add markdown formatting, extra spacing, or conversational text.

    OUTPUT FORMAT:
    CUSTOMER_STATED_PROBLEM: [Write the problem exactly as the customer described it, in a single sentence]
    IDENTIFIED_BUSINESS_PROBLEM: [Write the actual, underlying business problem that you have diagnosed]
    HIDDEN_ROOT_RISK: [Identify a latent or hidden risk/problem that the customer did not explicitly state but exists]
    CUSTOMER_CHAT_SUMMARY: [Write a comprehensive summary of the entire conversation; do not omit critical details]
    QUESTIONS_ASKED: [List every single question the Agent asked during the conversation, each on a new line, ending with a question mark]
    END_QUESTIONS
    """

    response = await llm.ainvoke(output_prompt)
    content = response.content

    # -----------------------------------------------
    # TEK SATIRLI ALANLARI PARSE ET
    # -----------------------------------------------
    def extract_field(text, field):
        try:
            start = text.find(f"{field}:") + len(f"{field}:")
            end = text.find("\n", start)
            if end == -1:
                end = len(text)
            return text[start:end].strip()
        except:
            return ""

    # -----------------------------------------------
    # ÇOKLU SATIRLI ALANLARI PARSE ET
    # -----------------------------------------------
    def extract_multiline_field(text, start_field, end_marker):
        try:
            start = text.find(f"{start_field}:") + len(f"{start_field}:")
            end = text.find(end_marker, start)
            if end == -1:
                end = len(text)
            return text[start:end].strip()
        except:
            return ""

    return {
        "status": "completed",
        "is_complete": True,
        "customer_stated_problem": extract_field(content, "CUSTOMER_STATED_PROBLEM"),
        "identified_business_problem": extract_field(content, "IDENTIFIED_BUSINESS_PROBLEM"),
        "hidden_root_risk": extract_field(content, "HIDDEN_ROOT_RISK"),
        "customer_chat_summary": extract_field(content, "CUSTOMER_CHAT_SUMMARY"),
        "questions_asked": extract_multiline_field(content, "QUESTIONS_ASKED", "END_QUESTIONS"),
        "message": "Problem keşif aşaması tamamlandı. Problem yapılandırma başlıyor...",
    }