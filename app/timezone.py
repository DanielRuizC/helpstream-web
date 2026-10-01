import pytz
from datetime import datetime
from typing import Optional

# Zona horaria oficial de la aplicación (HU18: America/Lima UTC-5)
LIMA_TZ = pytz.timezone("America/Lima")


def obtener_ahora_lima() -> datetime:
    """Retorna la fecha y hora actual en la zona horaria America/Lima (UTC-5)."""
    return datetime.now(LIMA_TZ)


def convertir_a_lima(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convierte cualquier datetime a la zona horaria America/Lima (UTC-5).
    - Si dt es None, retorna None.
    - Si dt es naive (sin tzinfo, como se almacena en PostgreSQL/SQLite por utcnow),
      se asume que representa UTC y se localiza y convierte a America/Lima.
    - Si dt ya cuenta con tzinfo, se convierte con astimezone a America/Lima.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Los datetimes almacenados en la base de datos están en UTC
        dt = pytz.utc.localize(dt)
    return dt.astimezone(LIMA_TZ)


def formatear_fecha_lima(dt: Optional[datetime], formato: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Formatea un datetime en cadena de texto representativa en hora local de Lima.
    Retorna '-' si el datetime es None.
    """
    if dt is None:
        return "-"
    dt_lima = convertir_a_lima(dt)
    return dt_lima.strftime(formato) if dt_lima else "-"


def convertir_lima_a_utc_naive(dt_local: datetime) -> datetime:
    """
    Convierte un datetime local de Lima a naive UTC para realizar consultas
    y filtros precisos en la base de datos (donde los registros están en UTC).
    """
    if dt_local.tzinfo is None:
        dt_local = LIMA_TZ.localize(dt_local)
    return dt_local.astimezone(pytz.utc).replace(tzinfo=None)
