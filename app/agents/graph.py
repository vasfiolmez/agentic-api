import logging
from typing import TypedDict, Literal, List
from langgraph.graph import StateGraph, END
from app.agents.peer_agent import run_peer_agent
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent
from app.agents.analysis_agent import run_analysis_agent
from app.agents.code_agent import run_code_agent

logger = logging.getLogger(__name__)


# -----------------------------------------------
# STATE: Konuşmanın hafızası
# Graph boyunca tüm node'lar bu state'i paylaşır
# -----------------------------------------------
class AgentState(TypedDict):
    task: str                    # Kullanıcının şu anki sorusu
    session_id: str              # Konuşma kimliği
    agent_type: str              # Hangi agent çalışacak
    conversation_history: List   # Tüm konuşma geçmişi
    original_task: str           # Kullanıcının ilk sorusu
    peer_result: dict            # Peer agent çıktısı
    discovery_result: dict       # Discovery agent çıktısı
    structuring_result: dict     # Structuring agent çıktısı
    problem_tree: dict           # Oluşturulan problem ağacı
    is_complete: bool            # Discovery tamamlandı mı?
    final_result: dict           # Kullanıcıya dönecek son sonuç


# -----------------------------------------------
# NODE 1: PEER AGENT NODE
# Graph'ın başlangıç noktası
# Kullanıcının isteğini analiz eder ve kategorize eder
# -----------------------------------------------
async def peer_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Peer Node çalışıyor. Task: {state['task']}")

    # Problem ağacı varsa has_problem_tree=True gönder
    has_problem_tree = bool(state.get("problem_tree"))
    result = await run_peer_agent(state["task"], has_problem_tree=has_problem_tree)
    state["peer_result"] = result

    if result.get("response_type") == "redirect":
        discovery_result = await run_discovery_agent(
            state["task"],
            state["conversation_history"],
        )
        result["discovery"] = discovery_result
        state["discovery_result"] = discovery_result

    state["final_result"] = result
    logger.info(f"[GRAPH] Peer Node tamamlandı. Kategori: {result.get('response_type')}")
    return state


# -----------------------------------------------
# NODE 2: DISCOVERY AGENT NODE
# Soru-cevap ile problemi derinlemesine anlar
# -----------------------------------------------
async def discovery_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Discovery Node çalışıyor.")

    result = await run_discovery_agent(
        state["original_task"],
        state["conversation_history"],
    )

    history = state["conversation_history"]
    history.append({"role": "agent", "content": result.get("message", "")})

    state["discovery_result"] = result
    state["conversation_history"] = history
    state["is_complete"] = result.get("is_complete", False)
    state["final_result"] = result

    logger.info(f"[GRAPH] Discovery Node tamamlandı. Tamamlandı mı: {state['is_complete']}")
    return state


# -----------------------------------------------
# NODE 3: STRUCTURING AGENT NODE
# Discovery çıktısını alır, problem ağacı oluşturur
# -----------------------------------------------
async def structuring_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Structuring Node çalışıyor.")

    result = await run_structuring_agent(state["discovery_result"])

    # Discovery ve structuring sonuçlarını birleştir
    final = state["discovery_result"].copy()
    final["structuring"] = result

    # Problem ağacını state'e kaydet
    # Sonraki sorularda Analysis Agent kullanacak
    state["structuring_result"] = result
    state["problem_tree"] = result
    state["final_result"] = final

    logger.info(f"[GRAPH] Structuring Node tamamlandı.")
    return state


# -----------------------------------------------
# NODE 4: ANALYSIS AGENT NODE
# Problem ağacı hakkındaki soruları cevaplar
# Daha önce oluşturulan problem ağacını context olarak kullanır
# -----------------------------------------------
async def analysis_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Analysis Node çalışıyor.")

    result = await run_analysis_agent(
        state["task"],
        state["problem_tree"],
    )

    state["final_result"] = result
    logger.info(f"[GRAPH] Analysis Node tamamlandı.")
    return state
# -----------------------------------------------
# NODE 5: CODE AGENT NODE
# Kod yazma taleplerini karşılar
# Temiz, çalışan ve açıklamalı kod üretir
# -----------------------------------------------
async def code_node(state: AgentState) -> AgentState:
    logger.info(f"[GRAPH] Code Node çalışıyor.")

    result = await run_code_agent(state["task"])

    state["final_result"] = result
    logger.info(f"[GRAPH] Code Node tamamlandı.")
    return state

# -----------------------------------------------
# ROUTER 1: Peer Node sonrası nereye gidecek?
# Peer node içinde discovery zaten başlatıldı
# Bu yüzden her zaman END'e gidiyoruz
# -----------------------------------------------
def route_peer(state: AgentState) -> Literal["analysis_node", "__end__"]:
    response_type = state["peer_result"].get("response_type", "")

    # Problem ağacı hakkında soru → analysis node'a git
    if response_type == "analysis":
        logger.info("[GRAPH] Peer → Analysis Node.")
        return "analysis_node"
    
    if response_type == "code":
        logger.info("[GRAPH] Peer → Code Node.")
        return "code_node"

    # Diğer durumlar → END
    logger.info(f"[GRAPH] Peer → END. Tip: {response_type}")
    return "__end__"


# -----------------------------------------------
# ROUTER 2: Discovery Node sonrası nereye gidecek?
# is_complete True ise → Structuring Node
# is_complete False ise → END (kullanıcı cevap bekliyor)
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
# -----------------------------------------------
def build_graph():
    graph = StateGraph(AgentState)

    # Node'ları ekle
    graph.add_node("peer_node", peer_node)
    graph.add_node("discovery_node", discovery_node)
    graph.add_node("structuring_node", structuring_node)
    graph.add_node("analysis_node", analysis_node)
    graph.add_node("code_node", code_node)

     # Peer Agent'ın kategorize ettiği response_type'a göre yönlendirme
     # Discovery → discovery_agent
     # Code → code_agent
     # Analysis → analysis_agent
     # Greeting → greeting_response (peer içinde direkt cevaplanacak)
     # Diğerleri → out_of_scope_response (peer içinde direkt cevaplanacak)


    # Başlangıç noktası
    graph.set_entry_point("peer_node")

    # Peer node'dan sonra:
    # ANALYSIS → analysis_node
    # Diğerleri → END
    graph.add_conditional_edges(
        "peer_node",
        route_peer,
        {
            "analysis_node": "analysis_node",
            "code_node": "code_node",
            "__end__": END,
        }
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

    # Structuring ve Analysis bittikten sonra her zaman END
    graph.add_edge("structuring_node", END)
    graph.add_edge("analysis_node", END)
    graph.add_edge("code_node", END)

    return graph.compile()


# Graph'ı oluştur ve dışa aktar
agent_graph = build_graph()