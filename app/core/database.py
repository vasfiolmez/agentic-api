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