from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GROQ_API_KEY: str
    TAVILY_API_KEY: str
    MONGODB_URL: str = "mongodb://mongodb:27017"
    DATABASE_NAME: str = "agentic_db"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()