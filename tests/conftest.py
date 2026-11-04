import pytest


@pytest.fixture(autouse=True)
def keep_llm_files_out_of_real_data(tmp_path, monkeypatch):
    """Tests that build the real planner must never write prompt or cache files into the user's data folder."""
    from training_agent.planner import llm_agent, llm_client
    monkeypatch.setattr(llm_client, "MANUAL_DIR", tmp_path / "llm_manual")
    monkeypatch.setattr(llm_agent, "CACHE_DIR", tmp_path / "llm_cache")
