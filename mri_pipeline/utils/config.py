import yaml
from pathlib import Path

def load_config(config_path="config.yaml"):
    config_path = Path(config_path)

    if not config_path.exists() or not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}