import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.models.schemas import TaskRequest
from app.agents.graph import agent_graph
from app.agents.discovery_agent import run_discovery_agent
from app.agents.structuring_agent import run_structuring_agent
from app.agents.peer_agent import run_peer_agent
from app.agents.analysis_agent import run_analysis_agent
from app.core.database import get_db, save_session, get_session
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agent/execute")
async def execute_agent(request: TaskRequest):

    # Boş görev kontrolü
    if not request.task or request.task.strip() == "":
        raise HTTPException(status_code=400, detail="Görev boş olamaz.")

    # Session ID oluştur veya mevcut olanı kullan
    session_id = request.session_id or str(uuid.uuid4())

    # -----------------------------------------------
    # SESSION'I MONGODB'DEN OKU
    # Bellekten değil MongoDB'den okuyoruz
    # Sunucu yeniden başlasa bile veriler kaybolmaz
    # -----------------------------------------------
    session_data = await get_session(session_id)

    # -----------------------------------------------
    # OTOMATİK AGENT SEÇİMİ
    # session_id yoksa → Peer Agent (yeni konuşma)
    # session_id var + tamamlanmadı → Discovery devam
    # session_id var + tamamlandı → Peer Agent (yeni soru)
    # -----------------------------------------------
    if session_data is None:
        agent_type = "peer_agent"
        logger.info(f"[ROUTES] Yeni session. Peer Agent başlatılıyor.")
    elif session_data.get("completed"):
        agent_type = "peer_agent"
        logger.info(f"[ROUTES] Discovery tamamlandı. Peer Agent başlatılıyor.")
    else:
        agent_type = "discovery_agent"
        logger.info(f"[ROUTES] Discovery devam ediyor.")

    logger.info(f"Session: {session_id} | Agent: {agent_type} | Task: {request.task}")

    try:
        # Session geçmişini al
        if session_data is None:
            session_data = {
                "session_id": session_id,
                "history": [],
                "original_task": request.task,
                "completed": False,
                "problem_tree": {},
            }

        # Kullanıcı mesajını geçmişe ekle
        history = session_data.get("history", [])
        history.append({"role": "user", "content": request.task})

        # -----------------------------------------------
        # PEER AGENT
        # -----------------------------------------------
        if agent_type == "peer_agent":

            problem_tree = session_data.get("problem_tree", {})

            if problem_tree:
                # -----------------------------------------------
                # Problem ağacı varsa → Peer Agent'a sor
                # has_problem_tree=True ile ANALYSIS kategorisi devreye girer
                # -----------------------------------------------
                peer_result = await run_peer_agent(request.task, has_problem_tree=True)

                if peer_result.get("response_type") == "analysis":
                    # Problem ağacı hakkında soru → Analysis Agent
                    logger.info("[ROUTES] ANALYSIS → Analysis Agent çalışıyor.")
                    result = await run_analysis_agent(request.task, problem_tree)

                    # Session'ı koru
                    await save_session(session_id, {
                        "history": history,
                        "original_task": session_data.get("original_task", request.task),
                        "completed": True,
                        "problem_tree": problem_tree,
                    })

                elif peer_result.get("response_type") == "redirect":
                    # Yeni problem → Discovery başlat
                    logger.info("[ROUTES] Yeni problem → Discovery başlatılıyor.")
                    discovery_result = await run_discovery_agent(request.task, [])
                    peer_result["discovery"] = discovery_result
                    result = peer_result

                    await save_session(session_id, {
                        "history": history,
                        "original_task": request.task,
                        "completed": False,
                        "problem_tree": {},
                    })

                else:
                    # Greeting, direct_answer, out_of_scope
                    result = peer_result

                    # Problem ağacı varsa koru
                    await save_session(session_id, {
                        "history": history,
                        "original_task": session_data.get("original_task", request.task),
                        "completed": True,
                        "problem_tree": problem_tree,
                    })

            else:
                # -----------------------------------------------
                # Problem ağacı yok → Normal LangGraph akışı
                # -----------------------------------------------
                initial_state = {
                    "task": request.task,
                    "session_id": session_id,
                    "agent_type": agent_type,
                    "conversation_history": history,
                    "original_task": request.task,
                    "peer_result": {},
                    "discovery_result": {},
                    "structuring_result": {},
                    "problem_tree": {},
                    "is_complete": False,
                    "final_result": {},
                }

                final_state = await agent_graph.ainvoke(initial_state)
                result = final_state.get("final_result", {})

                if result.get("response_type") == "redirect":
                    await save_session(session_id, {
                        "history": history,
                        "original_task": request.task,
                        "completed": False,
                        "problem_tree": {},
                    })
                else:
                    await save_session(session_id, {
                        "history": [],
                        "original_task": request.task,
                        "completed": False,
                        "problem_tree": {},
                    })

        # -----------------------------------------------
        # DISCOVERY AGENT: Direkt çalıştır
        # -----------------------------------------------
        elif agent_type == "discovery_agent":
            original_task = session_data.get("original_task", request.task)

            result = await run_discovery_agent(original_task, history)

            history.append({"role": "agent", "content": result.get("message", "")})

            is_done = result.get("is_complete", False)
            problem_tree = {}

            if is_done:
                structuring_result = await run_structuring_agent(result)
                result["structuring"] = structuring_result
                problem_tree = structuring_result

            await save_session(session_id, {
                "history": history,
                "original_task": original_task,
                "completed": is_done,
                "problem_tree": problem_tree,
            })

        else:
            raise HTTPException(status_code=400, detail="Bilinmeyen agent tipi.")



# Response type'a göre agent_type güncelle
        if isinstance(result, dict) and result.get("response_type") == "code":
            agent_type = "code_agent"
        elif isinstance(result, dict) and result.get("response_type") == "analysis":
            agent_type = "analysis_agent"
        # -----------------------------------------------
        # MONGODB'YE LOG KAYDET
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