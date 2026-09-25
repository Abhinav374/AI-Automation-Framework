import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CONFIG_PATH = BASE_DIR / "config.json"

load_dotenv(ENV_PATH)

KEYS = [
    "JIRA_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_ACCEPTANCE_FIELD",
    "GROQ_API_KEY",
    "GROQ_MODEL",
]


def read_config() -> dict:
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    config = {key: os.getenv(key, "") for key in KEYS}
    config.update({key: value for key, value in data.items() if key in KEYS})
    if not config.get("GROQ_MODEL"):
        config["GROQ_MODEL"] = "openai/gpt-oss-120b"
    return config


def write_config(updates: dict) -> dict:
    config = read_config()
    config.update({key: value.strip() if isinstance(value, str) else value for key, value in updates.items() if key in KEYS})
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config
