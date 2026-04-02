import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.models.schemas import TaskRequest, AgentType
from app.agents.peer_agent import run_peer_agent
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent
from app.core.database import get_db
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Oturum geçmişlerini bellekte tut
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
        # Hangi agent çalışacak?
        if request.agent_type == AgentType.PEER:
            result = await run_peer_agent(request.task)

            # Peer agent redirect dönüyorsa discovery başlat
            if result.get("response_type") == "redirect":
                session_store[session_id] = {
                    "agent": "discovery",
                    "history": [],
                    "original_task": request.task,
                }
                discovery_result = await run_discovery_agent(
                    request.task,
                    conversation_history=[],
                )
                result["discovery"] = discovery_result

        elif request.agent_type == AgentType.DISCOVERY:
            # Mevcut session geçmişini al
            session_data = session_store.get(session_id, {
                "history": [],
                "original_task": request.task,
                "completed":False,
            })
            if session_data.get("completed"):
                result = await run_peer_agent(request.task)
                return {
                    "session_id": session_id,
                    "agent_type": "peer_agent",
                    "result": result,
                }

            history = session_data.get("history", [])
            original_task = session_data.get("original_task", request.task)

            # Kullanıcı mesajını geçmişe ekle
            history.append({"role": "user", "content": request.task})

            # Discovery agent çalıştır
            result = await run_discovery_agent(original_task, history)

            # Agent cevabını geçmişe ekle
            history.append({"role": "agent", "content": result.get("message", "")})

            # Session'ı güncelle
            session_store[session_id] = {
                "agent": "discovery",
                "history": history,
                "original_task": original_task,
                "completed": result.get("is_complete", False),
            }

            # Discovery tamamlandıysa structuring başlat
            if result.get("is_complete"):
                structuring_result = await run_structuring_agent(result)
                result["structuring"] = structuring_result

        elif request.agent_type == AgentType.STRUCTURING:
            # Direkt structuring çalıştır
            session_data = session_store.get(session_id, {})
            if not session_data:
                raise HTTPException(
                    status_code=400,
                    detail="Önce Discovery Agent ile konuşma başlatmalısınız."
                )
            result = await run_structuring_agent(session_data)

        else:
            raise HTTPException(status_code=400, detail="Bilinmeyen agent tipi.")

        # MongoDB'ye kaydet
        db = get_db()
        if db is not None:
            log_entry = {
                "session_id": session_id,
                "agent_type": request.agent_type,
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