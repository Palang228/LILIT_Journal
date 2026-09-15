"""Конфигурация приложения"""
import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "Лилит"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

def validate_config(require_ai: bool = False):
    missing = [k for k, v in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }.items() if not v]
    if require_ai and not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise RuntimeError("Не заданы переменные окружения: " + ", ".join(missing))
