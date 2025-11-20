# configs.py
# Configuration loaded from environment variables.
# Keep sensitive values out of source control (use Heroku config vars or .env locally).

import os
from typing import Optional

API_ID: Optional[int] = None
API_HASH: Optional[str] = None
BOT_TOKEN: Optional[str] = None
LOG_CHANNEL: Optional[int] = None  # optional: channel id for logs
MONGO_URL: Optional[str] = None    # optional: mongodb if used

def _int_env(name: str) -> Optional[int]:
    val = os.getenv(name)
    return int(val) if val and val.isdigit() else None

API_ID = _int_env("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHANNEL = _int_env("LOG_CHANNEL")
MONGO_URL = os.getenv("MONGO_URL")

# Basic validation - will raise helpful errors early if missing
def validate():
    missing = []
    if API_ID is None:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them before starting the bot."
        )

if __name__ == "__main__":
    try:
        validate()
        print("configs loaded OK")
    except Exception as e:
        print("Configuration error:", e)
        raise
