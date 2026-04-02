import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.models.schemas import TaskRequest, AgentType
from app.agents.graph import agent_graph
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent
from app.core.database import get_db
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# -----------------------------------------------
# SESSION STORE
# Kullanıcıların konuşma geçmişini bellekte tutar
# -----------------------------------------------
session_store = {}


@router.post("/agent/execute")
async def execute_agent(request: TaskRequest):

    # Boş görev kontrolü
    if not request.task or request.task.strip() == "":
        raise HTTPException(status_code=400, detail="Görev boş olamaz.")

    # Session ID oluştur veya mevcut olanı kullan
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Session: {session_id} | Agent: {request.agent_type} | Task: {request.task}")

    try:
        # Mevcut session geçmişini al
        session_data = session_store.get(session_id, {
            "history": [],
            "original_task": request.task,
            "completed": False,
        })

        # Kullanıcı mesajını geçmişe ekle
        history = session_data.get("history", [])
        history.append({"role": "user", "content": request.task})

        # -----------------------------------------------
        # PEER AGENT: Graph ile çalıştır
        # -----------------------------------------------
        if request.agent_type == AgentType.PEER:

            # Discovery tamamlandıysa yeni soruyu peer'a yönlendir
            if session_data.get("completed"):
                logger.info("[ROUTES] Discovery tamamlandı, Peer Agent çalışıyor.")

            initial_state = {
                "task": request.task,
                "session_id": session_id,
                "agent_type": str(request.agent_type),
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
        # Graph'ı bypass et, discovery node'u çağır
        # -----------------------------------------------
        elif request.agent_type == AgentType.DISCOVERY:

            # Discovery tamamlandıysa peer'a yönlendir
            if session_data.get("completed"):
                logger.info("[ROUTES] Discovery tamamlandı, Peer Agent'a yönlendiriliyor.")
                from app.agents.peer_agent import run_peer_agent
                result = await run_peer_agent(request.task)
                session_store[session_id] = {
                    "history": history,
                    "original_task": session_data.get("original_task", request.task),
                    "completed": True,
                }
                return {
                    "session_id": session_id,
                    "agent_type": "peer_agent",
                    "result": result,
                }

            original_task = session_data.get("original_task", request.task)

            # Discovery agent'ı direkt çalıştır
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

        else:
            raise HTTPException(status_code=400, detail="Bilinmeyen agent tipi.")

        # -----------------------------------------------
        # MONGODB'YE KAYDET
        # -----------------------------------------------
        db = get_db()
        if db is not None:
            log_entry = {
                "session_id": session_id,
                "agent_type": str(request.agent_type),
                "input_task": request.task,
                "output": result,
                "timestamp": datetime.utcnow(),
                "status": "completed",
            }
            await db.task_logs.insert_one(log_entry)
            logger.info(f"MongoDB'ye kaydedildi. Session: {session_id}")

        return {
            "session_id": session_id,
            "agent_type": request.agent_type,
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent çalışırken hata oluştu: {str(e)}")