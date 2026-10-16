from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    rag_api_key: str = ""
    cypher_timeout_s: float = 5.0
    lightrag_timeout_s: float = 12.0

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    lightrag_working_dir: str = "./lightrag"
    lightrag_kv_storage: str = "JsonKVStorage"
    lightrag_vector_storage: str = "QdrantVectorDBStorage"
    lightrag_graph_storage: str = "NetworkXStorage"
    lightrag_doc_status_storage: str = "JsonDocStatusStorage"
    qdrant_url: str = "http://localhost:6333"
    qdrant_workspace: str = "ksp_iis"
    chunk_token_size: int = 1000
    chunk_overlap_token_size: int = 120

    llm_base_url: str = "http://localhost:8080"
    embed_base_url: str = "http://localhost:8081"
    rerank_base_url: str = "http://localhost:8082"
    embed_dim: int = 1024
    embed_max_tokens: int = 1024
    enable_rerank: bool = True

    @property
    def llm_chat_url(self) -> str:
        return f"{self.llm_base_url.rstrip('/')}/v1/chat/completions"

    @property
    def llm_tokenize_url(self) -> str:
        return f"{self.llm_base_url.rstrip('/')}/tokenize"

    @property
    def embed_url(self) -> str:
        return f"{self.embed_base_url.rstrip('/')}/v1/embeddings"

    @property
    def embed_tokenize_url(self) -> str:
        return f"{self.embed_base_url.rstrip('/')}/tokenize"

    @property
    def rerank_url(self) -> str:
        return f"{self.rerank_base_url.rstrip('/')}/v1/rerank"

    @property
    def rerank_health_url(self) -> str:
        return f"{self.rerank_base_url.rstrip('/')}/health"


@lru_cache
def get_settings() -> Settings:
    return Settings()
