import logging
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from app.core.config import settings

logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.3,
)

import os
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
search_tool = TavilySearch(max_results=3)

async def run_discovery_agent(task: str, conversation_history: list = []) -> dict:
    logger.info(f"Discovery Agent çalışıyor. Task: {task}")

    # Konuşma geçmişini formatla
    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            role = "Kullanıcı" if msg["role"] == "user" else "Agent"
            history_text += f"{role}: {msg['content']}\n"

    # Yeterli bilgi var mı kontrol et
    if conversation_history and len(conversation_history) >= 6:
        return await _generate_discovery_output(task, conversation_history)

    # Soru üret
    question_prompt = f"""
    Sen bir Business Sense Discovery Agent'sın.
    Görevin müşterinin business problemini derinlemesine anlamak için sorular sormaktır.
    
    KURALLAR:
    - Çözüm önerme, sadece soru sor
    - Her seferinde maksimum 2 soru sor
    - Önceki cevaplara göre follow-up sorular üret
    - Sorular kısa ve net olsun
    - Türkçe yaz
    
    Müşterinin ilk talebi: {task}
    
    Önceki konuşma:
    {history_text if history_text else "Henüz konuşma yok, ilk soruları sor."}
    
    Şimdi müşteriye 2 soru sor. Sadece soruları yaz, başka açıklama yapma.
    """

    response = await llm.ainvoke(question_prompt)

    return {
        "status": "questioning",
        "message": response.content,
        "is_complete": False,
    }


async def _generate_discovery_output(task: str, conversation_history: list) -> dict:
    logger.info("Discovery Agent çıktı üretiyor...")

    history_text = ""
    for msg in conversation_history:
        role = "Kullanıcı" if msg["role"] == "user" else "Agent"
        history_text += f"{role}: {msg['content']}\n"

    # Web'den ek bilgi al
    search_results = search_tool.invoke(task)
    web_content = "\n".join([r.get("content", "") for r in search_results if isinstance(r, dict)])

    output_prompt = f"""
    Sen bir Business Sense Discovery Agent'sın.
    Aşağıdaki müşteri konuşmasını analiz ederek yapılandırılmış çıktı üret.
    
    Müşterinin ilk talebi: {task}
    
    Tüm konuşma:
    {history_text}
    
    Web'den ek bilgi:
    {web_content}
    
    Şu formatta çıktı üret (Türkçe):
    
    CUSTOMER_STATED_PROBLEM: [müşterinin kendi ifadesiyle problemi]
    IDENTIFIED_BUSINESS_PROBLEM: [senin netleştirdiğin gerçek iş problemi]
    HIDDEN_ROOT_RISK: [müşterinin söylemediği ama risk oluşturan gizli problem]
    CUSTOMER_CHAT_SUMMARY: [tüm konuşmanın özeti, hiçbir detay kaybolmasın]
    """

    response = await llm.ainvoke(output_prompt)
    content = response.content

    # Parse et
    def extract_field(text, field):
        try:
            start = text.find(f"{field}:") + len(f"{field}:")
            end = text.find("\n", start)
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
        "message": "Problem keşif aşaması tamamlandı. Problem yapılandırma başlıyor...",
    }