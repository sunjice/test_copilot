"""应用配置，从 .env 与环境变量读取（pydantic-settings）。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """配置项均可用 .env 或环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # ── 数据库 ──
    DATABASE_URL: str = "postgresql+asyncpg://youlai:Youlai%402026@www.youlai.tech:15432/youlai_admin"

    # ── Redis ──
    REDIS_URL: str = "redis://:123456@www.youlai.tech:6379/0"

    # ── 认证 ──
    SESSION_TYPE: str = "jwt"
    JWT_SECRET_KEY: str = "SecretKey012345678901234567890123456789012345678901234567890123456789"
    ACCESS_TOKEN_TTL: int = 7200
    REFRESH_TOKEN_TTL: int = 604800
    ALLOW_MULTI_LOGIN: bool = True

    # ── MinIO ──
    MINIO_ENDPOINT: str = "111.229.83.153:9000"
    MINIO_ACCESS_KEY: str = "bybaddp7zyARpgNbEGKf"
    MINIO_SECRET_KEY: str = "p9rBdQZPBIJcMH23iyFkZkXmmawbmwPlk3JLlaaj"
    MINIO_BUCKET: str = "public"
    MINIO_SECURE: bool = False

    # ── 邮件 ──
    MAIL_USERNAME: str = "your-email@example.com"
    MAIL_PASSWORD: str = "123456"
    MAIL_FROM: str = "youlaitech@163.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.youlai.tech"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    # ── 限流 ──
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_IP_LIMIT: int = 1000     # IP 窗口内最大请求数
    RATE_LIMIT_IP_WINDOW: int = 60      # IP 滑动窗口大小（秒）

    # ── CORS ──
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── 文件上传 ──
    FILE_MAX_SIZE_MB: int = 50
    FILE_ALLOWED_TYPES: str = "jpg,jpeg,png,gif"

    # ── AI 服务（.env / 环境变量配置，替代旧的 DB 端 aiconfig 管理） ──
    AI_API_BASE: str = "https://api.deepseek.com"
    AI_API_KEY: str = ""
    AI_MODEL: str = "deepseek-chat"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 4096
    AI_BATCH_SIZE: int = 30

    # ── LLM 日志清理 ──
    LLM_LOG_RETENTION_DAYS: int = 180  # LLM 日志保留天数，超期自动删除

    # ── 调试 ──
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── 性能计时 ──
    TIMING_LOG_ENABLED: bool = True  # 控制 timing.log 是否启用

    # ── Elasticsearch ──
    ES_HOST: str = "http://localhost:9200"
    ES_INDEX_CASE: str = "tc_cases"
    ES_INDEX_BUG: str = "tc_bugs"

    # ── Milvus ──
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_CASE: str = "tc_cases"
    MILVUS_COLLECTION_BUG: str = "tc_bugs"

    # ── Embedding ──
    # 提供方：local / ollama / openai / azure，内置 provider 见
    # app/aitc/retrieval/common/embedding/（注册表模式，可扩展任意供应商）
    # 切换 provider 时注意 EMBEDDING_DIM 需与对应模型输出维度一致（Milvus collection 建好后不可改维度）
    EMBEDDING_PROVIDER: str = "local"
    # 本地模型目录（相对项目根），也兼容 HuggingFace 模型名（如 BAAI/bge-large-zh-v1.5）
    EMBEDDING_MODEL: str = "models/bge-large-zh-v1.5"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_DEVICE: str = "cpu"  # cpu / cuda

    # ── Ollama Embedding（EMBEDDING_PROVIDER=ollama 时生效） ──
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"  # 常用 bge-m3 / nomic-embed-text 等

    # ── OpenAI 兼容 Embedding（EMBEDDING_PROVIDER=openai，OpenAI 官方/通义千问/DeepSeek 等） ──
    # 通义千问（DashScope）示例：
    #   OPENAI_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    #   OPENAI_EMBEDDING_MODEL=text-embedding-v3
    OPENAI_EMBEDDING_BASE_URL: str = ""
    OPENAI_EMBEDDING_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-v3"

    # ── Azure OpenAI Embedding（EMBEDDING_PROVIDER=azure 时生效） ──
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = "https://your-resource.openai.azure.com"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    AZURE_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"


settings = Settings()
