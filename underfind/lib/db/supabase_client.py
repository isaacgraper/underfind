from supabase import create_client, Client
from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables from .env if present
load_dotenv()

_supabase: Optional[Client] = None


def _validate_env() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing Supabase configuration. Please set SUPABASE_URL and SUPABASE_KEY in your environment/.env"
        )
    return url, key


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url, key = _validate_env()
        _supabase = create_client(url, key)
    return _supabase


# Maintain backwards compatibility with existing imports
supabase = get_supabase()
