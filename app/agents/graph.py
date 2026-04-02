import logging
from typing import TypedDict, Literal, List
from langgraph.graph import StateGraph, END
from app.agents.peer_agent import run_peer_agent
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent

logger = logging.getLogger(__name__)


# -----------------------------------------------
# STATE: Konuşmanın hafızası
# Graph boyunca tüm node'lar bu state'i paylaşır
# Bir node state'i günceller, sonraki node güncel state'i okur
# Örnek: peer_node sonucu → discovery_node okur
# -----------------------------------------------
class AgentState(TypedDict):
    task: str                    # Kullanıcının şu anki sorusu
    session_id: str              # Konuşma kimliği (her oturum için benzersiz)
    agent_type: str              # Hangi agent çalışacak (peer, discovery, structuring)
    conversation_history: List   # Tüm konuşma geçmişi (soru-cevap listesi)
    original_task: str           # Kullanıcının ilk sorusu (discovery boyunca korunur)
    peer_result: dict            # Peer agent'ın ürettiği sonuç
    discovery_result: dict       # Discovery agent'ın ürettiği sonuç
    structuring_result: dict     # Structuring agent'ın ürettiği sonuç
    is_complete: bool            # Discovery tamamlandı mı? (True → structuring'e geç)
    final_result: dict           # Kullanıcıya dönecek son sonuç


# -----------------------------------------------
# NODE 1: PEER AGENT NODE
# Graph'ın başlangıç noktası
# Kullanıcının isteğini analiz eder ve kategorize eder
# Eğer REDIRECT ise → Discovery'nin ilk sorularını da başlatır
# -----------------------------------------------
async def peer_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Peer Node çalışıyor. Task: {state['task']}")

    # Peer agent'ı çalıştır
    result = await run_peer_agent(state["task"])

    # Peer sonucunu state'e kaydet
    state["peer_result"] = result

    # Eğer kategori REDIRECT ise (business problemi var)
    # Discovery agent'ı başlat ve ilk soruları al
    if result.get("response_type") == "redirect":
        # Discovery'nin ilk sorularını al
        discovery_result = await run_discovery_agent(
            state["task"],             # Kullanıcının sorusu
            state["conversation_history"],  # Konuşma geçmişi (şu an boş)
        )
        # Peer sonucuna discovery'nin ilk sorularını ekle
        result["discovery"] = discovery_result
        # Discovery sonucunu da state'e kaydet
        state["discovery_result"] = discovery_result

    # Kullanıcıya dönecek son sonucu güncelle
    state["final_result"] = result

    logger.info(f"[GRAPH] Peer Node tamamlandı. Kategori: {result.get('response_type')}")
    return state


# -----------------------------------------------
# NODE 2: DISCOVERY AGENT NODE
# Kullanıcıyla soru-cevap yaparak problemi derinlemesine anlar
# Her turda konuşma geçmişine bakarak yeni sorular üretir
# 6 mesaja ulaşınca otomatik tamamlanır
# -----------------------------------------------
async def discovery_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Discovery Node çalışıyor.")

    # Discovery agent'ı çalıştır
    # original_task: kullanıcının ilk sorusu (her turda aynı kalır)
    # conversation_history: tüm konuşma geçmişi
    result = await run_discovery_agent(
        state["original_task"],
        state["conversation_history"],
    )

    # Agent cevabını konuşma geçmişine ekle
    history = state["conversation_history"]
    history.append({"role": "agent", "content": result.get("message", "")})

    # State'i güncelle
    state["discovery_result"] = result
    state["conversation_history"] = history

    # is_complete: Discovery tamamlandıysa True olur
    # True olunca route_discovery fonksiyonu structuring'e yönlendirir
    state["is_complete"] = result.get("is_complete", False)
    state["final_result"] = result

    logger.info(f"[GRAPH] Discovery Node tamamlandı. Tamamlandı mı: {state['is_complete']}")
    return state


# -----------------------------------------------
# NODE 3: STRUCTURING AGENT NODE
# Discovery'nin ürettiği 4 çıktıyı alır
# Problem tipini ve problem ağacını oluşturur
# Bu node yeni soru sormaz, direkt analiz yapar
# -----------------------------------------------
async def structuring_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Structuring Node çalışıyor.")

    # Discovery sonucunu structuring agent'a gönder
    result = await run_structuring_agent(state["discovery_result"])

    # Discovery ve structuring sonuçlarını birleştir
    # Kullanıcı hem discovery hem structuring çıktısını görsün
    final = state["discovery_result"].copy()
    final["structuring"] = result

    # State'i güncelle
    state["structuring_result"] = result
    state["final_result"] = final

    logger.info(f"[GRAPH] Structuring Node tamamlandı.")
    return state


# -----------------------------------------------
# ROUTER 1: Peer Node sonrası nereye gidecek?
# Peer node içinde discovery zaten başlatıldı
# Bu yüzden her zaman END'e gidiyoruz
# Sonraki discovery turları routes.py'dan yönetiliyor
# -----------------------------------------------
def route_peer(state: AgentState) -> Literal["__end__"]:
    return "__end__"


# -----------------------------------------------
# ROUTER 2: Discovery Node sonrası nereye gidecek?
# is_complete True ise → Structuring Node'a git
# is_complete False ise → END'e git (kullanıcı cevap bekliyor)
# -----------------------------------------------
def route_discovery(state: AgentState) -> Literal["structuring_node", "__end__"]:
    if state.get("is_complete"):
        logger.info("[GRAPH] Discovery tamamlandı → Structuring.")
        return "structuring_node"
    logger.info("[GRAPH] Discovery devam ediyor → END.")
    return "__end__"


# -----------------------------------------------
# GRAPH KURULUMU
# Node'ları ve aralarındaki bağlantıları tanımlar
# Bu fonksiyon bir kez çalışır ve graph'ı oluşturur
# -----------------------------------------------
def build_graph():
    # Yeni bir graph oluştur
    # AgentState: graph boyunca taşınacak veri tipi
    graph = StateGraph(AgentState)

    # Node'ları graph'a ekle
    graph.add_node("peer_node", peer_node)
    graph.add_node("discovery_node", discovery_node)
    graph.add_node("structuring_node", structuring_node)

    # Başlangıç noktası: her zaman peer_node'dan başla
    graph.set_entry_point("peer_node")

    # Peer node'dan sonra her zaman END'e git
    graph.add_conditional_edges(
        "peer_node",
        route_peer,
        {"__end__": END}
    )

    # Discovery node'dan sonra:
    # is_complete True → structuring_node
    # is_complete False → END
    graph.add_conditional_edges(
        "discovery_node",
        route_discovery,
        {
            "structuring_node": "structuring_node",
            "__end__": END,
        }
    )

    # Structuring bittikten sonra her zaman END
    graph.add_edge("structuring_node", END)

    # Graph'ı derle ve döndür
    return graph.compile()


# -----------------------------------------------
# GRAPH'I OLUŞTUR
# Bu satır uygulama başladığında bir kez çalışır
# agent_graph diğer dosyalardan import edilir
# -----------------------------------------------
agent_graph = build_graph()