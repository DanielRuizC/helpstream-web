import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception as e:
        logger.error(f"[Supabase Client Error] Error al inicializar cliente de Supabase: {e}")


def get_supabase_client() -> Client:
    """
    Retorna la instancia del cliente de Supabase.
    Si aún no ha sido inicializada, la instancia utilizando las variables de entorno
    SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY con create_client.
    """
    global supabase
    if supabase is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError(
                "Las variables de entorno SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY "
                "deben estar configuradas en el entorno o archivo .env."
            )
        supabase = create_client(url, key)
    return supabase
