from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "jinaai/jina-embeddings-v3"
DEFAULT_EMBED_DIM = 1024
DEFAULT_CHUNK_TOKENS = 512


def _default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "kb-engine"


@dataclass(frozen=True)
class Config:
    vault_path: Path
    db_path: Path = field(default=None)  # type: ignore[assignment]
    model_name: str = DEFAULT_MODEL
    embed_dim: int = DEFAULT_EMBED_DIM
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS

    def __post_init__(self) -> None:
        if self.db_path is None:
            object.__setattr__(self, "db_path", _default_state_dir() / "kb-engine.db")

    @property
    def knowledge_dir(self) -> Path:
        return self.vault_path / "Knowledge"
