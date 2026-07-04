import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root path
ROOT_DIR = Path(__file__).resolve().parent

# Define directories
CREDENTIALS_DIR = ROOT_DIR / "credentials"
LOGS_DIR = ROOT_DIR / "logs"
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"

# Ensure directories exist
for directory in [CREDENTIALS_DIR, LOGS_DIR, DATA_DIR, ASSETS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# File paths
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"
LOG_FILE = LOGS_DIR / "app.log"

# Google API settings
# Scopes: gmail.modify allows reading, labeling, and marking emails as read/unread
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Gemini API settings
# Using gemini-1.5-flash for fast and cost-effective text analysis
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

# Retrieve API keys from env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# App Configurations
DEFAULT_MAX_EMAILS = 10
SUPPORTED_FILTERS = {
    "Unread": "is:unread",
    "Today": "newer_than:1d",
    "Last 7 Days": "newer_than:7d",
    "Starred": "is:starred",
    "Primary": "category:primary",
    "Important": "is:important",
    "Promotions": "category:promotions",
    "Social": "category:social",
}
