# configs.py
import os


BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID")) if os.environ.get("API_ID") else None
API_HASH = os.environ.get("API_HASH")


LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL")) if os.environ.get("LOG_CHANNEL") else None
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
TMP_DIR = os.environ.get("TMP_DIR", "/tmp")


if not BOT_TOKEN or not API_ID or not API_HASH:
raise RuntimeError("BOT_TOKEN, API_ID and API_HASH environment variables are required")
