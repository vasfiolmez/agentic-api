import os
import logging
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------
# LLM ve SEARCH TOOL KURULUMU
# -----------------------------------------------
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

search_tool = TavilySearch(max_results=3)


async def run_analysis_agent(task: str, problem_tree: dict) -> dict:
    logger.info(f"Analysis Agent çalışıyor. Task: {task}")

    # -----------------------------------------------
    # PROBLEM AĞACINI FORMATLA
    # Dict formatındaki problem ağacını okunabilir
    # metne çevir, LLM'e context olarak ver
    # -----------------------------------------------
    problem_tree_text = ""
    if problem_tree:
        problem_type = problem_tree.get("problem_type", "")
        main_problem = problem_tree.get("main_problem", "")
        problem_tree_text = f"Problem Tipi: {problem_type}\n"
        problem_tree_text += f"Ana Problem: {main_problem}\n\n"
        problem_tree_text += "Problem Ağacı:\n"

        for node in problem_tree.get("problem_tree", []):
            root_cause = node.get("root_cause", "")
            problem_tree_text += f"\n• {root_cause}\n"
            for sub_cause in node.get("sub_causes", []):
                problem_tree_text += f"  - {sub_cause}\n"

    # -----------------------------------------------
    # WEB'DEN EK BİLGİ AL
    # Kullanıcının sorusuna göre güncel bilgi çek
    # -----------------------------------------------
    search_results = search_tool.invoke(task)
    web_content = "\n".join(
        [r.get("content", "") for r in search_results if isinstance(r, dict)]
    )

    # -----------------------------------------------
    # ANALYSIS AGENT PROMPT
    # Problem ağacını context olarak kullanarak
    # kullanıcının sorusunu cevapla
    # -----------------------------------------------
    analysis_prompt = f"""
    Sen bir Problem Analysis Agent'sın.
    Görevin müşterinin daha önce oluşturulan problem ağacını analiz ederek
    sorularını cevaplamak ve derinlemesine içgörüler sunmaktır.
    
    KURALLAR:
    - Sadece problem ağacındaki bilgileri kullan
    - Gerekirse web'den aldığın bilgilerle zenginleştir
    - Kısa, net ve yapılandırılmış cevap ver
    - Yeni problem keşfi yapma
    - Türkçe yaz
    
    MEVCUT PROBLEM AĞACI:
    {problem_tree_text}
    
    WEB'DEN EK BİLGİ:
    {web_content}
    
    MÜŞTERİNİN SORUSU:
    {task}
    
    Soruyu problem ağacı bağlamında cevapla.
    """

    response = await llm.ainvoke(analysis_prompt)

    return {
        "response_type": "analysis",
        "message": response.content,
        "references": [r.get("url", "") for r in search_results if isinstance(r, dict)],
    }