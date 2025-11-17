from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "finance"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    ADMIN_SECRET_KEY: str = "dev-admin-secret-change-in-production"

    DB_NAME: str = "finance"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    ADD_BASE_ADMIN: bool = False

    OPENROUTER_API_KEY: str | None
    OPENROUTER_EMBED_MODEL: str = "qwen/qwen3-embedding-8b"
    OPENROUTER_EMBED_URL: str | None = None
    OPENROUTER_HTTP_REFERER: str | None = None
    OPENROUTER_APP_TITLE: str | None = None
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_CHAT_MODEL: str = "qwen/qwen3-235b-a22b-2507"
    OPENROUTER_CHAT_URL: str | None = None
    OPENROUTER_CHAT_TIMEOUT_SECONDS: float = 60.0
    OPENROUTER_CHAT_DEFAULT_TEMPERATURE: float = 0.2
    OPENROUTER_CHAT_DEFAULT_TOP_P: float = 0.9
    OPENROUTER_CHAT_DEFAULT_MAX_TOKENS: int = 1200

    RAG_MESSAGES_LIMIT: int = 20
    RAG_MAX_CONTEXT_CHARS: int = 50_000
    RAG_DEFAULT_TOP_K: int = 12
    RAG_DEFAULT_SCORE_THRESHOLD: float | None = 0.5
    RAG_USE_QUERY_EXPANSION: bool = True
    RAG_RRF_K: int = 60
    RAG_ORCHESTRATOR_CONFIDENCE_THRESHOLD: float = 0.6
    RAG_ORCHESTRATOR_HISTORY_TAIL: int = 5
    RAG_CLARIFICATIONS_LIMIT: int = 3

    RAG_ORCHESTRATOR_TEMPERATURE: float = 0.0
    RAG_ORCHESTRATOR_TOP_P: float = 1.0
    RAG_ORCHESTRATOR_MAX_TOKENS: int = 400

    RAG_FUSION_TEMPERATURE: float = 0.2
    RAG_FUSION_TOP_P: float = 0.95
    RAG_FUSION_MAX_TOKENS: int = 500

    RAG_ANSWER_TEMPERATURE: float = 0.2
    RAG_ANSWER_TOP_P: float = 0.9
    RAG_CHUNKS_MAX_TOKENS: int = 1200
    RAG_FULL_CONTEXT_MAX_TOKENS: int = 1500
    RAG_GENERAL_TEMPERATURE: float = 0.3
    RAG_GENERAL_TOP_P: float = 0.9
    RAG_GENERAL_MAX_TOKENS: int = 900
    RAG_CLARIFICATION_TEMPERATURE: float = 0.2
    RAG_CLARIFICATION_TOP_P: float = 0.9
    RAG_CLARIFICATION_MAX_TOKENS: int = 400
    RAG_TOOL_HISTORY_TAIL: int = 5

    RAG_KB_COLLECTION_NAME: str = "knowledge_base_chunks"
    RAG_KB_USER_ID: int = 0
    RAG_KB_LIMIT: int = 6
    RAG_KB_SCORE_THRESHOLD: float | None = 0.6

    CBR_API_BASE_URL: str = "https://cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
    CBR_CACHE_TTL_SECONDS: int = 900
    TAVILY_API_KEY: str | None = "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"
    TAVILY_BASE_URL: str = "https://api.tavily.com/search"
    TAVILY_TIMEOUT_SECONDS: float = 8.0
    TAVILY_CACHE_TTL_SECONDS: int = 300

    QDRANT_URL: str | None = "http://178.72.149.75:6333"
    QDRANT_COLLECTION_NAME: str = "document_chunks"
    QDRANT_BATCH_SIZE: int = 64

    MINIO_ENDPOINT: str | None = "http://178.72.149.75:9000"
    MINIO_ACCESS_KEY: str | None = "minioadmin"
    MINIO_SECRET_KEY: str | None = "minioadmin"
    MINIO_BUCKET_NAME: str = "documents"
    MINIO_REGION: str | None = None
    MINIO_PUBLIC_ENDPOINT: str | None = "http://178.72.149.75:9001"
    MINIO_USE_SSL: bool = False

    @property
    def db_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
