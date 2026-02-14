class Constants:
    """Constants used by agents and config.

    Includes default values and environment variable keys
    commonly referenced by agent modules.
    """

    # App
    APP_NAME: str = "Smart Document Organizer"
    DEFAULT_ENV: str = "development"
    DEFAULT_TIMEOUT_SECONDS: int = 30
    ENV_KEY: str = "ENV"

    # Security
    API_KEY_NAME: str = "API_KEY"  # used by Start.py auth header check

    # Vector / memory
    VECTOR_COLLECTION: str = "documents"
    VECTOR_DIMENSION: int = 384
    VECTOR_DIMENSION_KEY: str = "VECTOR_DIMENSION"
    MEMORY_NAMESPACE: str = "legal_ai_agent_registry"
    VECTOR_USE_ST_KEY: str = "VECTOR_USE_ST"
    VECTOR_EMBEDDING_MODEL_KEY: str = "VECTOR_EMBEDDING_MODEL"

    # Agent feature flags (env variable names)
    AGENTS_ENABLE_LEGAL_REASONING: str = "AGENTS_ENABLE_LEGAL_REASONING"
    AGENTS_ENABLE_ENTITY_EXTRACTOR: str = "AGENTS_ENABLE_ENTITY_EXTRACTOR"
    AGENTS_ENABLE_IRAC: str = "AGENTS_ENABLE_IRAC"
    AGENTS_ENABLE_TOULMIN: str = "AGENTS_ENABLE_TOULMIN"
    AGENTS_ENABLE_REGISTRY: str = "AGENTS_ENABLE_REGISTRY"
    AGENTS_CACHE_TTL_KEY: str = "AGENTS_CACHE_TTL_SECONDS"
    AGENTS_CACHE_TTL_SECONDS: int = 300

    # Memory approval thresholds
    MEMORY_APPROVAL_THRESHOLD_KEY: str = "MEMORY_APPROVAL_THRESHOLD"
    MEMORY_APPROVAL_THRESHOLD_DEFAULT: float = 0.7
