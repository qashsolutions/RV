"""
Supabase client wrapper used by all backend pipelines.
"""

from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_SERVICE_KEY


def get_client() -> Client:
    """Get a Supabase client using the service_role key (full write access)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. "
            "Add them as GitHub Actions secrets or in a .env file."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
