from pathlib import Path
from kb_engine.config import Config


def test_default_db_path_is_under_state_dir(tmp_path):
    cfg = Config(vault_path=tmp_path)
    assert cfg.vault_path == tmp_path
    assert cfg.db_path.name == "kb-engine.db"
    assert cfg.model_name == "jinaai/jina-embeddings-v3"
    assert cfg.embed_dim == 1024


def test_knowledge_dir_scopes_to_knowledge_subfolder(tmp_path):
    cfg = Config(vault_path=tmp_path)
    assert cfg.knowledge_dir == tmp_path / "Knowledge"
