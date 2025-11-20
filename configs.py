import os

# Core bot credentials (required)
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Database (required for MongoDB features)
MONGODB_URI = os.environ.get("MONGODB_URI", "")

# Optional: Add other vars if your bot uses them (e.g., log channel)
# LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", -1001234567890))  # Replace with your ID
# STORAGE_LIMIT = int(os.environ.get("STORAGE_LIMIT", 10485760))  # In MB, default 10GB
