"""应用配置文件"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI SaaS API"
    app_version: str = "1.0.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://redis:6379/0"
    allowed_origins: list[str] = ["*"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
