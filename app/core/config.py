from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemma-2-9b-it:free"

    class Config:
        env_file = ".env"

settings = Settings()
