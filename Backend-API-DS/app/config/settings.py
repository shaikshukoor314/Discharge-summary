from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cortex_discharge_summary"

    # MinIO Configuration
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "cortex-documents"

    # Celery Configuration (optional, for future use)
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # JWT Authentication Configuration
    jwt_secret_key: str = "your-super-secret-key-change-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours

    # OCR Configuration
    ocr_provider: str = "chandra"
    chandra_ocr_url: str = "http://101.53.140.236:8080"
    ocr_max_tokens: int = 7000
    ocr_fallback_enabled: bool = True
    ocr_fallback_dir: str = "./pipeline_outputs/OCR_output_pages"

    # Spell Check Configuration
    spellcheck_dictionary_path: str | None = None
    spellcheck_enabled: bool = True
    groq_api_key: str | None = None

    # De-identification Configuration
    deid_ruleset_path: str | None = None
    deid_enabled: bool = True
    deid_use_ensemble: bool = True

    # Pipeline Configuration
    pipeline_cleanup_on_new_run: bool = True
    store_results_in_minio: bool = True
    store_results_in_db: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
