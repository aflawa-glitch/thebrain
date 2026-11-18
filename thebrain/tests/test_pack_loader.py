import json
from app.core.pack_loader import load_packs

def test_load_packs(tmp_path):
    source_root = tmp_path / "source"
    app_config_dir = tmp_path / "config"
    app_config_dir.mkdir(parents=True)
    
    # Write config/packs.json
    with open(app_config_dir / "packs.json", "w") as f:
        json.dump({"mounted_packs": ["media-gen"]}, f)
        
    # Create the pack
    pack_dir = source_root / "packs" / "media-gen"
    pack_dir.mkdir(parents=True)
    with open(pack_dir / "pack.json", "w") as f:
        json.dump({"pack_id": "media-gen", "enabled": True}, f)
        
    packs = load_packs(source_root, app_config_dir)
    assert len(packs) == 1
    assert packs[0]["pack_id"] == "media-gen"
