import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.models.schemas import TaskRequest
from app.agents.graph import agent_graph
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent
from app.agents.peer_agent import run_peer_agent
from app.core.database import get_db
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# -----------------------------------------------
# SESSION STORE
# Kullanıcıların konuşma geçmişini bellekte tutar
# session_id → {history, original_task, completed}
# -----------------------------------------------
session_store = {}


@router.post("/agent/execute")
async def execute_agent(request: TaskRequest):

    # Boş görev kontrolü
    if not request.task or request.task.strip() == "":
        raise HTTPException(status_code=400, detail="Görev boş olamaz.")

    # Session ID oluştur veya mevcut olanı kullan
    session_id = request.session_id or str(uuid.uuid4())

    # -----------------------------------------------
    # OTOMATİK AGENT SEÇİMİ
    # session_id yoksa → yeni konuşma → Peer Agent
    # session_id var + tamamlanmadı → Discovery devam
    # session_id var + tamamlandı → Peer Agent (yeni soru)
    # -----------------------------------------------
    session_data = session_store.get(session_id, None)

    if session_data is None:
        # Yeni konuşma → Peer Agent
        agent_type = "peer_agent"
        logger.info(f"[ROUTES] Yeni session. Peer Agent başlatılıyor.")
    elif session_data.get("completed"):
        # Discovery tamamlandı → Peer Agent
        agent_type = "peer_agent"
        logger.info(f"[ROUTES] Discovery tamamlandı. Peer Agent başlatılıyor.")
    else:
        # Discovery devam ediyor
        agent_type = "discovery_agent"
        logger.info(f"[ROUTES] Discovery devam ediyor.")

    logger.info(f"Session: {session_id} | Agent: {agent_type} | Task: {request.task}")

    try:
        # Session geçmişini al
        if session_data is None:
            session_data = {
                "history": [],
                "original_task": request.task,
                "completed": False,
            }

        # Kullanıcı mesajını geçmişe ekle
        history = session_data.get("history", [])
        history.append({"role": "user", "content": request.task})

        # -----------------------------------------------
        # PEER AGENT: LangGraph ile çalıştır
        # -----------------------------------------------
        if agent_type == "peer_agent":
            initial_state = {
                "task": request.task,
                "session_id": session_id,
                "agent_type": agent_type,
                "conversation_history": history,
                "original_task": request.task,
                "peer_result": {},
                "discovery_result": {},
                "structuring_result": {},
                "is_complete": False,
                "final_result": {},
            }

            # LangGraph graph'ı çalıştır
            final_state = await agent_graph.ainvoke(initial_state)
            result = final_state.get("final_result", {})

            # Eğer redirect ise session'ı discovery moduna al
            if result.get("response_type") == "redirect":
                session_store[session_id] = {
                    "history": history,
                    "original_task": request.task,
                    "completed": False,
                }
            else:
                session_store[session_id] = {
                    "history": history,
                    "original_task": request.task,
                    "completed": False,
                }

        # -----------------------------------------------
        # DISCOVERY AGENT: Direkt çalıştır
        # -----------------------------------------------
        elif agent_type == "discovery_agent":
            original_task = session_data.get("original_task", request.task)

            # Discovery agent'ı çalıştır
            result = await run_discovery_agent(original_task, history)

            # Agent cevabını geçmişe ekle
            history.append({"role": "agent", "content": result.get("message", "")})

            # Discovery tamamlandıysa structuring başlat
            is_done = result.get("is_complete", False)
            if is_done:
                structuring_result = await run_structuring_agent(result)
                result["structuring"] = structuring_result

            # Session'ı güncelle
            session_store[session_id] = {
                "history": history,
                "original_task": original_task,
                "completed": is_done,
            }

        # -----------------------------------------------
        # MONGODB'YE KAYDET
        # -----------------------------------------------
        db = get_db()
        if db is not None:
            log_entry = {
                "session_id": session_id,
                "agent_type": agent_type,
                "input_task": request.task,
                "output": result,
                "timestamp": datetime.utcnow(),
                "status": "completed",
            }
            await db.task_logs.insert_one(log_entry)
            logger.info(f"MongoDB'ye kaydedildi. Session: {session_id}")

        return {
            "session_id": session_id,
            "agent_type": agent_type,
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent çalışırken hata oluştu: {str(e)}")