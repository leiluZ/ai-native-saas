"""网关配置"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "OpenAI Compatible API Gateway"
    app_version: str = "1.0.0"
    debug: bool = False

    gateway_api_key: str = "sk-gateway-default-key"
    rate_limit_per_minute: int = 60
    rate_limit_window_seconds: int = 60

    global_timeout: float = 120.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    retry_backoff_max: float = 30.0

    health_check_interval: int = 30
    health_check_timeout: float = 5.0

    heartbeat_interval: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
