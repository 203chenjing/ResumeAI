"""配置管理：从环境变量加载，支持 .env 文件。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Limits
    max_file_size_mb: int = 10
    session_timeout_minutes: int = 60 * 24 * 90  # 90 天，保留多岗位定制存档
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3
    llm_timeout_seconds: int = 60

    # 定时爬虫（默认开启，设 CRAWL_SCHEDULE_ENABLED=false 关闭）
    crawl_schedule_enabled: bool = True
    crawl_schedule_hour: int = 8
    crawl_schedule_minute: int = 0
    crawl_schedule_client_id: str = "default"

    # 六层记忆架构（见 docs/memory-architecture.md）
    memory_summary_threshold: int = 12
    autodream_min_hours: int = 24
    autodream_min_sessions: int = 5
    memory_index_max_lines: int = 200
    memory_index_max_bytes: int = 25600


settings = Settings()
