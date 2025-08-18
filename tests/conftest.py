import os
import sys
from pathlib import Path

# Minimal env variables so importing settings does not fail
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("ADMIN_USER_IDS", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
