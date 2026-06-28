from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://agentrouter.org/v1"
    AI_MODEL: str = "glm-5.2"
    AI_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"

    class Config:
        env_file = ".env"

settings = Settings()
