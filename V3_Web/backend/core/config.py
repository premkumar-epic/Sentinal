from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    backend_title: str = "SENTINALv1 API"
    backend_cors_origins: list[str] = ["*"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
