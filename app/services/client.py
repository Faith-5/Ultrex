import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
POLLINATIONS_BASE = os.getenv("POLLINATIONS_BASE")
POLLINATION_API_KEY = os.getenv("POLLINATION_API_KEY")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment variables.")

if not POLLINATION_API_KEY:
    raise ValueError("POLLINATION_API_KEY is not set in environment variables.")

if not TURSO_AUTH_TOKEN or not TURSO_DATABASE_URL:
    raise ValueError("TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in environment variables.")

client = Groq(api_key = GROQ_API_KEY)