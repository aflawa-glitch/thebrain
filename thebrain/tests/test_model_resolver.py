import json
from app.core.model_resolver import resolve_model

def test_resolve_model(tmp_path):
    source_root = tmp_path / "source"
    app_config_dir = tmp_path / "config"
    source_root.mkdir()
    app_config_dir.mkdir()
    
    # Write registry
    reg_dir = source_root / "config"
    reg_dir.mkdir()
    reg = {
        "models": [{"id": "qwen-test", "role": "primary", "status": "verified"}],
        "active_by_role": {"primary": "qwen-test"}
    }
    with open(reg_dir / "model-registry.json", "w") as f:
        json.dump(reg, f)
        
    model = resolve_model(source_root, app_config_dir, "primary")
    assert model["id"] == "qwen-test"
