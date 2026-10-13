from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "Automatic Calling API"
    API_V1_STR: str = "/api/v1"
    
    # VN Doctor Backend URL
    VN_DOCTOR_API_BASE_URL: str = "https://api-navi-doctor.tomotek.vn/api"
    
    # AI Provider Settings
    AI_PROVIDER: Literal["OPENAI", "GEMINI"] = "GEMINI"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    
    # Session TTL (5 phút mặc định)
    SESSION_TTL_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
