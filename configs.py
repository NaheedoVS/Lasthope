# configs.py
import os

API_ID = int(os.environ.get("API_ID", "0"))        # set on Heroku: heroku config:set API_ID=12345
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")       # if you use MongoDB
LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "")

# Example fallback / validation
if not BOT_TOKEN or API_ID == 0 or API_HASH == "":
    # Do not crash on import; raise a helpful error when starting
    raise RuntimeError("Missing required environment variables: BOT_TOKEN, API_ID, API_HASH")
