import json
import pathlib
from typing import Any

def resolve_model(source_root: pathlib.Path, app_config_dir: pathlib.Path, role: str = "primary") -> dict[str, Any]:
    registry_path = source_root / "config" / "model-registry.json"
    app_models_path = app_config_dir / "models.json"
    
    if not registry_path.exists():
        raise ValueError(f"Global model registry not found at {registry_path}")
        
    with open(registry_path) as f:
        registry = json.load(f)
        
    preferred_id = None
    if app_models_path.exists():
        with open(app_models_path) as f:
            app_models = json.load(f)
            preferred_id = app_models.get("preferred_by_role", {}).get(role)
            
    if not preferred_id:
        preferred_id = registry.get("active_by_role", {}).get(role)
        
    if not preferred_id:
        raise ValueError(f"No active model found for role '{role}'")
        
    for m in registry.get("models", []):
        if m["id"] == preferred_id:
            if m["status"] != "verified":
                raise ValueError(f"Model '{preferred_id}' is not verified.")
            return m
            
    raise ValueError(f"Model '{preferred_id}' not found in registry.")
