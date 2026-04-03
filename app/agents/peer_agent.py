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

os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
search_tool = TavilySearch(max_results=3)

PEER_AGENT_PROMPT = """
Sen bir Business Peer Agent'sın. Görevin kullanıcının talebini analiz etmek ve doğru aksiyonu almaktır.

Kullanıcının talebi 3 kategoriden birine girer:

1. DIRECT_ANSWER: Business bilgi sorusu (rekabet analizi, pazar trendleri, sektör bilgisi)
   → İnternetten ara, kısa ve net cevap ver, referansları ekle.

2. REDIRECT: Business problemi içeriyor (satış düşüşü, maliyet artışı, operasyonel sorun)
   → Kullanıcıyı Discovery Agent'a yönlendir, soru sorma.

3. OUT_OF_SCOPE: Business dışı talep (tarif, eğlence, günlük yaşam vb.)
   → Sistemin business odaklı çalıştığını açıkla, örnek business soruları sun.

Kullanıcının talebi: {task}

Önce kategoriyi belirle, sonra aksiyonu al.
Cevabını şu formatta ver:
KATEGORI: [DIRECT_ANSWER/REDIRECT/OUT_OF_SCOPE]
MESAJ: [cevabın]
REFERANSLAR: [varsa kaynaklar, yoksa boş bırak]
"""


async def run_peer_agent(task: str, has_problem_tree: bool = False) -> dict:
    logger.info(f"Peer Agent çalışıyor. Task: {task}")

    # Önce kategoriyi belirle
    if has_problem_tree:
        category_prompt = f"""
        Kullanıcının daha önce oluşturulmuş bir problem ağacı var.
        Aşağıdaki talebi analiz et ve sadece kategori adını yaz:
        
        - ANALYSIS: Problem ağacındaki herhangi bir konu, ana neden, alt neden hakkında soru veya açıklama isteği. Bu kategoriyi seç eğer soru problem ağacıyla ilgiliyse.
        - REDIRECT: Tamamen yeni ve farklı bir business problemi (öncekiyle alakasız yeni bir sorun)
        - GREETING: Selamlama, teşekkür, vedalaşma
        - DIRECT_ANSWER: Problem ağacıyla alakasız genel business bilgi sorusu
        - OUT_OF_SCOPE: Yemek, film, müzik gibi tamamen iş dışı konular
        
        ÖNEMLİ: Eğer soruda "ana neden", "açıklar mısın", "detay ver", "nedir" gibi ifadeler varsa ve problem ağacıyla ilgiliyse mutlaka ANALYSIS seç!
        
        Talep: {task}
        Sadece kategori adını yaz.
        """
    else:
        category_prompt = f"""
        Aşağıdaki talebi analiz et ve sadece kategori adını yaz:
        - DIRECT_ANSWER: Business bilgi sorusu (rekabet, pazar, sektör trendleri)
        - REDIRECT: Business problemi (satış düşüşü, maliyet, operasyonel sorun)
        - CODE: Kod yazma, script, algoritma veya yazılım geliştirme talebi
        - OUT_OF_SCOPE: Business dışı talep (yemek tarifi, eğlence, günlük yaşam)
        - GREETING: Selamlama, teşekkür, vedalaşma
        
        Talep: {task}
        Sadece kategori adını yaz.
        """

    category_response = await llm.ainvoke(category_prompt)
    category = category_response.content.strip().upper()

    logger.info(f"Peer Agent kategori: {category}")

    if "DIRECT_ANSWER" in category:
        # Web'de ara
        search_results = search_tool.invoke(task)
        references = [r.get("url", "") for r in search_results if isinstance(r, dict)]
        content = "\n".join([r.get("content", "") for r in search_results if isinstance(r, dict)])

        answer_prompt = f"""
        Kullanıcı şunu sordu: {task}
        
        Web'den bulunan bilgiler:
        {content}
        
        Kısa, net ve yapılandırılmış bir business cevabı ver. Türkçe yaz.
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
    
    elif "ANALYSIS" in category:
        # Problem ağacı hakkında soru
        # routes.py bu kategoriyi yakalayıp Analysis Agent'a yönlendirecek
        return {
            "response_type": "analysis",
            "message": "",
            "references": [],
            "redirected_to": "analysis_agent",
        }
    
    elif "GREETING" in category:
        greeting_prompt = f"""
        Kullanıcı şunu söyledi: {task}
        
        KURALLAR:
        - Kullanıcının mesajına uygun şekilde karşılık ver
        - Eğer teşekkür ettiyse → teşekkürü kabul et
        - Eğer selamlama yaptıysa → selamla
        - Eğer vedalaştıysa → güle güle de
        - "Merhaba" ile başlama, kullanıcının mesajına göre doğal bir giriş yap
        - Kısa ve samimi ol
        - Gerekirse başka bir business sorusu sormaya davet et
        - Türkçe yaz
        """
        greeting_response = await llm.ainvoke(greeting_prompt)
        return {
            "response_type": "greeting",
            "message": greeting_response.content,
            "references": [],
            "redirected_to": None,
        }
    

    else:
        out_of_scope_prompt = f"""
        Kullanıcı şunu istedi: {task}
        
        Bu sistem sadece business ve strateji problemleri için tasarlanmıştır.
        Kullanıcıya bunu nazikçe açıkla ve aynı konuyu business perspektifine çevirebileceği 2-3 örnek soru sun.
        Türkçe yaz.
        """
        response = await llm.ainvoke(out_of_scope_prompt)

        return {
            "response_type": "out_of_scope",
            "message": response.content,
            "references": [],
            "redirected_to": None,
        }