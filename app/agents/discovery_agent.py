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
    # Liste halindeki mesajları okunabilir metne çevir
    # Örnek: "Kullanıcı: Satışlarım düşüyor\nAgent: Ne zamandır?"
    # -----------------------------------------------
    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            role = "Kullanıcı" if msg["role"] == "user" else "Agent"
            history_text += f"{role}: {msg['content']}\n"

    # -----------------------------------------------
    # YETERLİ BİLGİ KONTROLÜ
    # 6 mesaja ulaşınca (yaklaşık 3 soru-cevap turu)
    # soru sormayı bırak, çıktı üretmeye geç
    # -----------------------------------------------
    if conversation_history and len(conversation_history) >= 6:
        return await _generate_discovery_output(task, conversation_history)

    # -----------------------------------------------
    # SORU ÜRET
    # Müşterinin cevaplarına göre follow-up sorular üret
    # Konuşma geçmişi yoksa ilk soruları sor
    # -----------------------------------------------
    question_prompt = f"""
    Sen bir Business Sense Discovery Agent'sın.
    Görevin müşterinin business problemini derinlemesine anlamak için sorular sormaktır.
    
    KURALLAR:
    - Çözüm önerme, sadece soru sor
    - Her seferinde maksimum 2 soru sor
    - Önceki cevaplara göre follow-up sorular üret
    - Sorular kısa ve net olsun
    - Türkçe yaz
    
    PROBLEM TANIMLAMA SORULARI (bu konularda soru sor):
    - Şu an yaşadığınız ana işi aksatan problem nedir?
    - Bu problem hangi departmanı doğrudan etkiliyor?
    - Bu sorun ilk ne zaman ortaya çıktı?
    - Şu an bu problemi nasıl yönetiyorsunuz?
    
    GERÇEK İHTİYAÇ SORULARI (bu konularda soru sor):
    - Çözüm mü istiyorsunuz yoksa önce sebebi mi anlamak istiyorsunuz?
    - Bugüne kadar denediğiniz çözümler neler oldu? Neden başarısız oldu?
    - Aslında çözüme mi ihtiyacınız var yoksa görünürlük mü eksik?
    
    ÖRNEK MÜŞTERİ CEVAPLARI VE BAĞLAMLARI:
    
    Pazarlama Kaynaklı Problem:
    - "Reklamlarımız eskisi kadar performans göstermiyor"
    - "Hedef kitlemize doğru ulaşamıyoruz"
    - "Dijital kampanyalarımızın dönüşüm oranı çok düşük"
    - "Pazarlama bütçemizi verimli kullanamıyoruz"
    
    Rekabet Kaynaklı Problem:
    - "Rakiplerimiz bizden daha agresif fiyatlar sunuyor"
    - "Rakipler yeni özellikler çıkardı, biz geride kaldık"
    - "Müşteriler rakiplerin kampanyalarına yöneliyor"
    - "Pazar son 1 yılda çok sıkılaştı"
    
    Ürün ve Değer Önerisi Kaynaklı Problem:
    - "Ürünümüz artık müşterilerin beklentilerini tam karşılamıyor olabilir"
    - "Ürün farklılaşması konusunda rakiplerin gerisinde kaldık"
    - "Yeni müşteriler ürünün değerini anlamakta zorlanıyor"
    - "Fiyat-değer dengemiz müşterilere yüksek geliyor"
    
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

    # -----------------------------------------------
    # KONUŞMA GEÇMİŞİNİ FORMATLA
    # -----------------------------------------------
    history_text = ""
    for msg in conversation_history:
        role = "Kullanıcı" if msg["role"] == "user" else "Agent"
        history_text += f"{role}: {msg['content']}\n"

    # -----------------------------------------------
    # WEB'DEN EK BİLGİ AL
    # Tavily ile konuyla ilgili güncel bilgi çek
    # -----------------------------------------------
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
    
    CUSTOMER_STATED_PROBLEM: [müşterinin kendi ifadesiyle problemi tek cümleyle yaz]
    IDENTIFIED_BUSINESS_PROBLEM: [senin netleştirdiğin gerçek iş problemi]
    HIDDEN_ROOT_RISK: [müşterinin söylemediği ama risk oluşturan gizli problem]
    CUSTOMER_CHAT_SUMMARY: [tüm konuşmanın özeti, hiçbir detay kaybolmasın]
    QUESTIONS_ASKED: [konuşmada Agent tarafından sorulan tüm soruları tek tek yaz, her soru yeni satırda, soru işareti ile bitsin]
    END_QUESTIONS
    
    ÖNEMLİ:
    - Her alan için sadece o alanın içeriğini yaz
    - QUESTIONS_ASKED boş bırakma, tüm soruları yaz
    - QUESTIONS_ASKED bittikten sonra END_QUESTIONS yaz
    """

    response = await llm.ainvoke(output_prompt)
    content = response.content

    # -----------------------------------------------
    # TEK SATIRLI ALANLARI PARSE ET
    # field: değer formatındaki alanları çıkar
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
    # QUESTIONS_ASKED gibi çok satır içeren alanlar için
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
        # Çok satırlı alan — END_QUESTIONS marker'ına kadar al
        "questions_asked": extract_multiline_field(content, "QUESTIONS_ASKED", "END_QUESTIONS"),
        "message": "Problem keşif aşaması tamamlandı. Problem yapılandırma başlıyor...",
    }