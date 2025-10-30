import os, yaml
from pydantic import BaseModel

class Config(BaseModel):
    env: str
    account: dict
    symbols: list[str]
    sessions: dict
    execution: dict
    risk: dict
    edges: dict
    news: dict
    ipc: dict
    logging: dict
    alerts: dict
    infra: dict

def load_config(path="config/config.yaml") -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # env overrides
    for k, v in os.environ.items():
        if k == "LOG_LEVEL":
            raw["logging"]["level"] = v
    return Config(**raw)
