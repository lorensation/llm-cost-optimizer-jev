import json
from pathlib import Path

from app.config import AppConfig

path = Path("artifacts/schemas/config.schema.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(AppConfig.model_json_schema(), indent=2), encoding="utf-8")
print(path)

