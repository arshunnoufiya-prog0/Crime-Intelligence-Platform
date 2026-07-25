from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_path: str = "./models/Qwen2.5-4B-Instruct-Q8_0.gguf"
    ctx_size: int = 8192
    n_gpu_layers: int = -1
    n_parallel: int = 4
    batch_size: int = 512
    ubatch_size: int = 512
    threads: int = 8
    flash_attn: bool = True

    # Zero-hallucination defaults
    temperature: float = 0.0
    top_k: int = 1
    top_p: float = 1.0
    repeat_penalty: float = 1.15
    min_p: float = 0.05

    host: str = "0.0.0.0"
    port: int = 8080
    api_key: str = ""

    llama_server_bin: str = "./bin/llama-server"


settings = Settings()
