from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

client = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    logger.info("MongoDB bağlantısı kuruldu.")


async def close_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB bağlantısı kapatıldı.")


def get_db():
    return db


# -----------------------------------------------
# SESSION CRUD FONKSİYONLARI
# Session verilerini MongoDB'ye kaydet ve oku
# Bellekten farklı olarak sunucu yeniden başlasa
# bile veriler kaybolmaz
# -----------------------------------------------

async def save_session(session_id: str, session_data: dict):
    """Session'ı MongoDB'ye kaydet"""
    try:
        db = get_db()
        if db is None:
            return
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "session_id": session_id,
                **session_data
            }},
            upsert=True  # Yoksa oluştur, varsa güncelle
        )
        logger.info(f"Session kaydedildi: {session_id}")
    except Exception as e:
        logger.error(f"Session kaydetme hatası: {str(e)}")


async def get_session(session_id: str) -> dict:
    """Session'ı MongoDB'den oku"""
    try:
        db = get_db()
        if db is None:
            return None
        session = await db.sessions.find_one({"session_id": session_id})
        if session:
            # MongoDB'nin _id alanını kaldır
            session.pop("_id", None)
            return session
        return None
    except Exception as e:
        logger.error(f"Session okuma hatası: {str(e)}")
        return None


async def delete_session(session_id: str):
    """Session'ı MongoDB'den sil"""
    try:
        db = get_db()
        if db is None:
            return
        await db.sessions.delete_one({"session_id": session_id})
        logger.info(f"Session silindi: {session_id}")
    except Exception as e:
        logger.error(f"Session silme hatası: {str(e)}")