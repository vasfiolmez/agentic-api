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

PROBLEM_TYPES = [
    "Growth",
    "Cost",
    "Operational",
    "Technology",
    "Regulation",
    "Organizational",
    "Hybrid",
]


async def run_structuring_agent(discovery_output: dict) -> dict:
    logger.info("Structuring Agent running...")

    customer_stated_problem = discovery_output.get("customer_stated_problem", "")
    identified_business_problem = discovery_output.get("identified_business_problem", "")
    hidden_root_risk = discovery_output.get("hidden_root_risk", "")
    customer_chat_summary = discovery_output.get("customer_chat_summary", "")

    # -----------------------------------------------
    # GET ADDITIONAL WEB INFORMATION
    # -----------------------------------------------
    search_results = search_tool.invoke(identified_business_problem)
    web_content = "\n".join(
        [r.get("content", "") for r in search_results if isinstance(r, dict)]
    )

    structuring_prompt = f"""
    You are a Problem Structuring & Diagnosis Agent.
    Your goal is to analyze the given information and build a structured problem tree.
    
    RULES:
    - Do NOT ask new questions
    - Analyze directly and generate output
    - Identify 3-5 root causes
    - Write 2-3 sub-causes for each root cause
    - Keep all fields maximum 5 words — short, concise and clear
    - Respond in Turkish language
    
    INPUTS:
    Customer stated problem: {customer_stated_problem}
    Identified business problem: {identified_business_problem}
    Hidden root risk: {hidden_root_risk}
    Conversation summary: {customer_chat_summary}
    
    Additional web information:
    {web_content}
    
    Possible problem types: {", ".join(PROBLEM_TYPES)}
    
    Generate output in this exact format:
    
    PROBLEM_TIPI: [write only one of: Growth, Cost, Operational, Technology, Regulation, Organizational, Hybrid]
    ANA_PROBLEM: [main problem title, maximum 5 words]
    
    ANA_NEDEN_1: [first root cause, maximum 5 words]
    ALT_NEDEN_1_1: [maximum 5 words, concise and clear]
    ALT_NEDEN_1_2: [maximum 5 words, concise and clear]
    ALT_NEDEN_1_3: [maximum 5 words, concise and clear]
    
    ANA_NEDEN_2: [second root cause, maximum 5 words]
    ALT_NEDEN_2_1: [maximum 5 words, concise and clear]
    ALT_NEDEN_2_2: [maximum 5 words, concise and clear]
    ALT_NEDEN_2_3: [maximum 5 words, concise and clear]
    
    ANA_NEDEN_3: [third root cause, maximum 5 words]
    ALT_NEDEN_3_1: [maximum 5 words, concise and clear]
    ALT_NEDEN_3_2: [maximum 5 words, concise and clear]
    ALT_NEDEN_3_3: [maximum 5 words, concise and clear]
    
    ANA_NEDEN_4: [fourth root cause, maximum 5 words]
    ALT_NEDEN_4_1: [maximum 5 words, concise and clear]
    ALT_NEDEN_4_2: [maximum 5 words, concise and clear]
    
    ANA_NEDEN_5: [fifth root cause, maximum 5 words]
    ALT_NEDEN_5_1: [maximum 5 words, concise and clear]
    ALT_NEDEN_5_2: [maximum 5 words, concise and clear]
    
    IMPORTANT RULES:
    - NEVER write Growth, Cost, Operational, Technology, Regulation, Organizational, Hybrid anywhere except PROBLEM_TIPI
    - Every field must be maximum 5 words
    - Write short, concise and clear
    - Correct example: "Hedefleme yanlış", "Reklam optimizasyonu zayıf"
    - Wrong example: "Müşterinin dijital reklam stratejisinin verimsiz olmasi nedeniyle maliyetler artmistir"
    - ALT_NEDEN fields can never be empty
    """

    response = await llm.ainvoke(structuring_prompt)
    content = response.content

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
    # BUILD PROBLEM TREE
    # Filter out problem type keywords from sub-causes
    # -----------------------------------------------
    problem_tree = []
    for i in range(1, 6):
        ana_neden = extract_field(content, f"ANA_NEDEN_{i}")
        if not ana_neden:
            continue

        sub_causes = []
        for j in range(1, 4):
            alt_neden = extract_field(content, f"ALT_NEDEN_{i}_{j}")
            if alt_neden and alt_neden not in PROBLEM_TYPES:
                sub_causes.append(alt_neden)

        problem_tree.append({
            "root_cause": ana_neden,
            "sub_causes": sub_causes,
        })

    return {
        "problem_type": extract_field(content, "PROBLEM_TIPI"),
        "main_problem": extract_field(content, "ANA_PROBLEM"),
        "problem_tree": problem_tree,
    }