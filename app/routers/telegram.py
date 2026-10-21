import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks, status, HTTPException
from ..services.telegram_service import procesar_update_telegram

logger = logging.getLogger("helpstream.telegram.router")

router = APIRouter(
    prefix="/api/telegram",
    tags=["Telegram Webhook"]
)


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Webhook para recibir actualizaciones de Telegram Bot",
    description=(
        "Recibe updates entrantes enviados por Telegram (mensajes de texto y CallbackQuery). "
        "Opera bajo un modelo stateless sincronizado con Supabase."
    )
)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Endpoint principal del webhook de Telegram.

    - Recibe el payload JSON del Update de Telegram.
    - Discrimina entre mensajes de texto y eventos de CallbackQuery.
    - Procesa la lógica de negocio de manera asíncrona en segundo plano para responder
      inmediatamente con HTTP 200 OK a los servidores de Telegram, evitando reintentos.
    """
    try:
        update: Dict[str, Any] = await request.json()
    except Exception as e:
        logger.error(f"[Telegram Webhook] Error al parsear JSON del payload: {e}")
        # Telegram requiere HTTP 200 para no reintentar envíos corruptos
        return {"status": "error", "message": "Invalid JSON"}

    update_id = update.get("update_id")
    tipo_evento = "desconocido"
    if "message" in update:
        tipo_evento = "message (texto/comando)"
    elif "callback_query" in update:
        tipo_evento = "callback_query (botón interactivo)"

    logger.info(f"[Telegram Webhook] Update recibido [ID: {update_id}] - Tipo: {tipo_evento}")

    # Ejecutar procesamiento asíncrono con BackgroundTasks para latencia < 50ms hacia Telegram
    background_tasks.add_task(procesar_update_telegram, update)

    return {"status": "ok", "update_id": update_id, "tipo": tipo_evento}


@router.get("/health", summary="Verificación de estado del módulo Telegram")
def telegram_health():
    """Endpoint ligero para verificar disponibilidad del router de Telegram."""
    return {"status": "online", "service": "Telegram ITSM Bot for HelpStream"}
