import json
import pathlib
from typing import Any

def load_packs(source_root: pathlib.Path, app_config_dir: pathlib.Path) -> list[dict[str, Any]]:
    packs_config = app_config_dir / "packs.json"
    if not packs_config.exists():
        return []
    
    with open(packs_config) as f:
        config = json.load(f)
        
    mounted = config.get("mounted_packs", [])
    loaded_packs = []
    
    for pack_id in mounted:
        pack_dir = source_root / "packs" / pack_id
        pack_json = pack_dir / "pack.json"
        if not pack_json.exists():
            raise ValueError(f"Mounted pack '{pack_id}' not found at {pack_json}")
        with open(pack_json) as f:
            loaded_packs.append(json.load(f))
            
    return loaded_packs
