import os
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

os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
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
    logger.info("Structuring Agent çalışıyor...")

    customer_stated_problem = discovery_output.get("customer_stated_problem", "")
    identified_business_problem = discovery_output.get("identified_business_problem", "")
    hidden_root_risk = discovery_output.get("hidden_root_risk", "")
    customer_chat_summary = discovery_output.get("customer_chat_summary", "")

    # Web'den ek bilgi al
    search_results = search_tool.invoke(identified_business_problem)
    web_content = "\n".join(
        [r.get("content", "") for r in search_results if isinstance(r, dict)]
    )

    structuring_prompt = f"""
    Sen bir Problem Structuring & Diagnosis Agent'sın.
    Görevin verilen bilgileri analiz ederek problemi yapılandırmak ve problem ağacı oluşturmaktır.
    
    KURALLAR:
    - Yeni soru sorma
    - Direkt analiz yap ve çıktı üret
    - 3-5 ana neden belirle
    - Her ana neden için 2-3 alt neden yaz
    - Türkçe yaz
    - Alt nedenler kısa ve öz olmalı, maksimum 5-7 kelime
    - Alt nedenler tek cümle değil, kısa bir başlık gibi olmalı
    - Örnek doğru alt neden: "Hedefleme yanlış", "Reklam optimizasyonu zayıf"
    - Örnek yanlış alt neden: "Müşterinin dijital reklam stratejisinin hiệu quả olmaması nedeniyle maliyetler artmıştır"
    
    GİRDİLER:
    Müşterinin ifade ettiği problem: {customer_stated_problem}
    Netleştirilmiş iş problemi: {identified_business_problem}
    Gizli kök risk: {hidden_root_risk}
    Konuşma özeti: {customer_chat_summary}
    
    Web'den ek bilgi:
    {web_content}
    
    Olası problem tipleri: {", ".join(PROBLEM_TYPES)}
    
    Şu formatta çıktı üret:
    
    PROBLEM_TIPI: [sadece şunlardan birini yaz: Growth, Cost, Operational, Technology, Regulation, Organizational, Hybrid]
    ANA_PROBLEM: [ana problem başlığı]
    
    ANA_NEDEN_1: [birinci ana neden]
    ALT_NEDEN_1_1: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_1_2: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_1_3: [somut ve açıklayıcı bir cümle]
    
    ANA_NEDEN_2: [ikinci ana neden]
    ALT_NEDEN_2_1: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_2_2: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_2_3: [somut ve açıklayıcı bir cümle]
    
    ANA_NEDEN_3: [üçüncü ana neden]
    ALT_NEDEN_3_1: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_3_2: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_3_3: [somut ve açıklayıcı bir cümle]
    
    ANA_NEDEN_4: [dördüncü ana neden]
    ALT_NEDEN_4_1: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_4_2: [somut ve açıklayıcı bir cümle]
    
    ANA_NEDEN_5: [beşinci ana neden]
    ALT_NEDEN_5_1: [somut ve açıklayıcı bir cümle]
    ALT_NEDEN_5_2: [somut ve açıklayıcı bir cümle]
    
    ÖNEMLİ KURALLAR:
    - PROBLEM_TIPI dışında hiçbir yere Growth, Cost, Operational, Technology, Regulation, Organizational, Hybrid yazma
    - Her ALT_NEDEN mutlaka somut bir cümle olmalı, tek kelime olamaz
    - ALT_NEDEN alanları hiçbir zaman boş kalamaz
    - Eğer yeterli alt neden bulamazsan ana nedenin farklı boyutlarını düşünerek alt nedenler oluşturabilirsin
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

    # Problem ağacını oluştur
    problem_tree = []
    for i in range(1, 6):
        ana_neden = extract_field(content, f"ANA_NEDEN_{i}")
        if not ana_neden:
            continue

        sub_causes = []
        for j in range(1, 4):
            alt_neden = extract_field(content, f"ALT_NEDEN_{i}_{j}")
            # Boş değilse ve PROBLEM_TYPES listesinde değilse ekle
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