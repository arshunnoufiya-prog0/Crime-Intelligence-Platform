from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "crime-graph-rag"
    port: int = 9000
    api_key: str = ""

    llm_base_url: str = "http://localhost:8080"
    llm_timeout_s: int = 120
    temperature: float = 0.0
    top_k: int = 1
    top_p: float = 1.0
    repeat_penalty: float = 1.15

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"
    neo4j_database: str = "neo4j"
    vector_index_name: str = "fir_embedding_index"
    vector_dim: int = 1024
    vector_similarity_fn: str = "cosine"

    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"

    similarity_threshold: float = 0.65
    subgraph_max_hops: int = 2
    subgraph_max_nodes: int = 200

    enable_ocr: bool = False

    def synthesis_params(self) -> dict:
        """Zero-hallucination sampling preset used by summarizer."""
        return {
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
        }


settings = Settings()