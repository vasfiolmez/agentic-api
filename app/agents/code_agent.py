import os
import logging
from langchain_groq import ChatGroq
from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------
# LLM KURULUMU
# Code Agent için LLM bağlantısı
# -----------------------------------------------
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.1,  # Kod üretimi için düşük temperature
)


async def run_code_agent(task: str) -> dict:
    logger.info(f"Code Agent çalışıyor. Task: {task}")

    # -----------------------------------------------
    # CODE AGENT PROMPT
    # Profesyonel, çalışan ve açıklamalı kod üretir
    # Temperature düşük tutuldu → tutarlı kod çıktısı
    # -----------------------------------------------
    code_prompt = f"""
    Sen bir uzman yazılım geliştirici asistanısın.
    Görevin kullanıcının istediği kodu yazmaktır.
    
    KURALLAR:
    - Çalışan, temiz ve okunabilir kod yaz
    - Kodun başına kısa bir açıklama ekle
    - Kod bloklarını ``` ile işaretle
    - Gerekirse kullanım örneği göster
    - Türkçe açıklama yaz, kod İngilizce olabilir
    - Hata yönetimi ekle (try/except)
    - Best practice'leri uygula
    
    KULLANICININ İSTEĞİ:
    {task}
    
    Kodu yaz ve kısaca açıkla.
    """

    response = await llm.ainvoke(code_prompt)

    return {
        "response_type": "code",
        "message": response.content,
        "references": [],
        "redirected_to": None,
    }