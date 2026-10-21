import os
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
from ..utils.supabase_client import get_supabase_client

logger = logging.getLogger("helpstream.telegram")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Expresión regular estándar para validación de formato de correo corporativo
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Sedes corporativas válidas requeridas
SEDES_DISPONIBLES = ["San Isidro", "Callao", "Planta Chancay"]


# ============================================================================
# COMUNICACIÓN CON TELEGRAM BOT API (HTTPX ASÍNCRONO)
# ============================================================================

async def send_telegram_message(
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: str = "Markdown"
) -> bool:
    """
    Envía un mensaje a un chat de Telegram de forma asíncrona usando httpx.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.error("[Telegram] TELEGRAM_BOT_TOKEN no configurado en variables de entorno.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"[Telegram] Error al enviar mensaje: {resp.status_code} - {resp.text}")
                # Fallback sin parse_mode por si fallan caracteres especiales de Markdown
                if parse_mode:
                    payload.pop("parse_mode", None)
                    fallback_resp = await client.post(url, json=payload)
                    return fallback_resp.status_code == 200
                return False
            return True
    except Exception as e:
        logger.exception(f"[Telegram] Excepción al enviar mensaje a chat_id {chat_id}: {e}")
        return False


async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
) -> bool:
    """
    Responde a un CallbackQuery para detener el indicador de carga en el cliente Telegram.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"[Telegram] Error al responder callback_query {callback_query_id}: {e}")
        return False


def build_inline_keyboard_sedes() -> Dict[str, Any]:
    """
    Construye el InlineKeyboardMarkup interactivo con los botones de sedes requeridos.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🏢 San Isidro", "callback_data": "sede:San Isidro"},
                {"text": "⚓ Callao", "callback_data": "sede:Callao"}
            ],
            [
                {"text": "🏭 Planta Chancay", "callback_data": "sede:Planta Chancay"}
            ]
        ]
    }


def es_correo_valido(correo: str) -> bool:
    """Valida sintaxis de correo electrónico."""
    if not correo or not isinstance(correo, str):
        return False
    return bool(EMAIL_REGEX.match(correo.strip()))


# ============================================================================
# GESTIÓN DE ESTADO STATELESS CON SUPABASE (PostgreSQL)
# ============================================================================

def obtener_sesion(chat_id: int) -> Optional[Dict[str, Any]]:
    """Consulta la sesión activa de un chat_id en la tabla telegram_sesiones."""
    try:
        supabase = get_supabase_client()
        res = supabase.table("telegram_sesiones").select("*").eq("chat_id", chat_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"[Supabase] Error al consultar sesión para chat_id {chat_id}: {e}")
        return None


def upsert_sesion(
    chat_id: int,
    correo_usuario: Optional[str] = None,
    paso_actual: str = "esperando_correo",
    datos_temporales: Optional[Dict[str, Any]] = None
) -> bool:
    """Inserta o actualiza el registro de sesión en telegram_sesiones."""
    try:
        supabase = get_supabase_client()
        payload = {
            "chat_id": chat_id,
            "correo_usuario": correo_usuario,
            "paso_actual": paso_actual,
            "datos_temporales": datos_temporales if datos_temporales is not None else {}
        }
        supabase.table("telegram_sesiones").upsert(payload).execute()
        return True
    except Exception as e:
        logger.error(f"[Supabase] Error en upsert de sesión para chat_id {chat_id}: {e}")
        return False


def actualizar_sesion(chat_id: int, campos: Dict[str, Any]) -> bool:
    """Actualiza campos específicos de una sesión existente."""
    try:
        supabase = get_supabase_client()
        supabase.table("telegram_sesiones").update(campos).eq("chat_id", chat_id).execute()
        return True
    except Exception as e:
        logger.error(f"[Supabase] Error al actualizar sesión chat_id {chat_id}: {e}")
        return False


def eliminar_sesion(chat_id: int) -> bool:
    """Elimina el registro de la sesión en telegram_sesiones para reiniciar el ciclo."""
    try:
        supabase = get_supabase_client()
        supabase.table("telegram_sesiones").delete().eq("chat_id", chat_id).execute()
        return True
    except Exception as e:
        logger.error(f"[Supabase] Error al eliminar sesión para chat_id {chat_id}: {e}")
        return False


def insertar_ticket(correo: str, descripcion: str, sede: str) -> Optional[Dict[str, Any]]:
    """
    Inserta el nuevo ticket en la tabla tickets de Supabase.
    Asocia el usuario_id si el correo coincide con un registro en la tabla usuarios.
    """
    try:
        supabase = get_supabase_client()

        # Determinar usuario_id a partir del correo si existe en la BD
        usuario_id = 1
        try:
            user_query = supabase.table("usuarios").select("id").eq("correo", correo.strip().lower()).execute()
            if user_query.data and len(user_query.data) > 0:
                usuario_id = user_query.data[0]["id"]
        except Exception as e_user:
            logger.warning(f"[Supabase] No se pudo resolver usuario_id por correo: {e_user}")

        ticket_payload = {
            "usuario_id": usuario_id,
            "correo_solicitante": correo.strip().lower(),
            "descripcion": descripcion.strip(),
            "sede": sede.strip(),
            "estado": "Abierto",
            "criticidad": "Medio",
            "fecha_creacion": datetime.utcnow().isoformat(),
            "palabras_clave": "telegram, ticket, soporte"
        }

        res = supabase.table("tickets").insert(ticket_payload).execute()
        logger.info(f"[Supabase] Ticket insertado con éxito para {correo} en sede {sede}.")
        return res.data[0] if (res.data and len(res.data) > 0) else ticket_payload
    except Exception as e:
        logger.exception(f"[Supabase] Error al registrar ticket en tickets: {e}")
        return None


# ============================================================================
# LÓGICA DE NEGOCIO Y ÁRBOL DE DECISIONES CONVERSACIONAL
# ============================================================================

async def procesar_update_telegram(update: Dict[str, Any]) -> None:
    """
    Punto de entrada para el procesamiento del webhook de Telegram.
    Discrimina entre mensajes de texto y eventos de CallbackQuery (botones).
    """
    try:
        if "message" in update:
            await _procesar_mensaje_texto(update["message"])
        elif "callback_query" in update:
            await _procesar_callback_query(update["callback_query"])
        else:
            logger.debug(f"[Telegram] Update no manejado (tipo ignorado): {list(update.keys())}")
    except Exception as e:
        logger.exception(f"[Telegram] Error inesperado procesando update {update.get('update_id')}: {e}")


async def _procesar_mensaje_texto(message: Dict[str, Any]) -> None:
    """Procesa los mensajes de texto entrantes."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    texto = (message.get("text") or "").strip()

    if not chat_id:
        return

    # Comando /start: Reinicia el flujo en cualquier momento (Paso 0)
    if texto.startswith("/start"):
        await _ejecutar_paso_0_inicio(chat_id)
        return

    # Consultar sesión actual en Supabase
    sesion = obtener_sesion(chat_id)

    # Si no hay sesión previa y no es /start, invitar a iniciar
    if not sesion:
        msg = (
            "👋 ¡Hola! Para registrar una incidencia o requerimiento en **HelpStream**, "
            "por favor escribe */start* para iniciar el asistente."
        )
        await send_telegram_message(chat_id, msg)
        return

    paso_actual = sesion.get("paso_actual", "esperando_correo")

    # ------------------------------------------------------------------------
    # PASO 1: Validar correo corporativo (esperando_correo)
    # ------------------------------------------------------------------------
    if paso_actual == "esperando_correo":
        if not es_correo_valido(texto):
            msg_error = (
                "⚠️ *Correo inválido*\n\n"
                "El texto ingresado no tiene formato de correo electrónico.\n"
                "Por favor, ingresa tu correo corporativo (ej. `nombre@empresa.com`):"
            )
            await send_telegram_message(chat_id, msg_error)
            return

        correo_limpio = texto.lower()
        actualizar_sesion(chat_id, {
            "correo_usuario": correo_limpio,
            "paso_actual": "esperando_descripcion"
        })

        msg_pregunta = (
            f"✅ Correo registrado: `{correo_limpio}`\n\n"
            "📝 *¿Cuál es tu problema?*\n"
            "Por favor, describe con detalle el inconveniente técnico que presentas:"
        )
        await send_telegram_message(chat_id, msg_pregunta)
        return

    # ------------------------------------------------------------------------
    # PASO 2: Guardar descripción y solicitar sede (esperando_descripcion)
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_descripcion":
        if len(texto) < 5:
            msg_corta = (
                "⚠️ La descripción es muy breve.\n"
                "Por favor, describe con un poco más de detalle el problema:"
            )
            await send_telegram_message(chat_id, msg_corta)
            return

        datos_actuales = sesion.get("datos_temporales") or {}
        datos_actuales["descripcion"] = texto

        actualizar_sesion(chat_id, {
            "datos_temporales": datos_actuales,
            "paso_actual": "esperando_sede"
        })

        teclado = build_inline_keyboard_sedes()
        msg_sede = (
            "📍 *Selección de Sede*\n\n"
            "Por favor, pulsa el botón correspondiente a la sede donde ocurre la incidencia:"
        )
        await send_telegram_message(chat_id, msg_sede, reply_markup=teclado)
        return

    # ------------------------------------------------------------------------
    # PASO 3: Estado esperando_sede pero el usuario envió texto en vez de botón
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_sede":
        teclado = build_inline_keyboard_sedes()
        msg_recordatorio = (
            "⚠️ Por favor, utiliza uno de los botones inferiores para seleccionar tu sede "
            "o escribe */start* para reiniciar el proceso:"
        )
        await send_telegram_message(chat_id, msg_recordatorio, reply_markup=teclado)
        return

    else:
        # Estado desconocido -> reiniciar a paso 0
        await _ejecutar_paso_0_inicio(chat_id)


async def _procesar_callback_query(callback: Dict[str, Any]) -> None:
    """
    Procesa las pulsaciones de botones InlineKeyboardMarkup (Paso 3: esperando_sede).
    """
    callback_id = callback.get("id")
    if callback_id:
        await answer_callback_query(callback_id)

    chat_id = (
        callback.get("message", {}).get("chat", {}).get("id")
        or callback.get("from", {}).get("id")
    )
    raw_data = (callback.get("data") or "").strip()

    if not chat_id:
        return

    # Normalizar valor de la sede seleccionada (admite prefijo 'sede:' o texto directo)
    sede_seleccionada = raw_data.replace("sede:", "").strip()

    if sede_seleccionada not in SEDES_DISPONIBLES:
        logger.warning(f"[Telegram] Callback recibido con sede no reconocida: {raw_data}")
        return

    sesion = obtener_sesion(chat_id)
    if not sesion or sesion.get("paso_actual") != "esperando_sede":
        msg_expirado = (
            "⚠️ Esta solicitud ya fue completada o la sesión ha expirado.\n"
            "Escribe */start* para crear un nuevo ticket."
        )
        await send_telegram_message(chat_id, msg_expirado)
        return

    correo_usuario = sesion.get("correo_usuario") or "usuario@helpstream.com"
    datos_temporales = sesion.get("datos_temporales") or {}
    descripcion = datos_temporales.get("descripcion", "Sin descripción provista")

    # Insertar ticket en Supabase
    ticket_creado = insertar_ticket(
        correo=correo_usuario,
        descripcion=descripcion,
        sede=sede_seleccionada
    )

    ticket_id = (ticket_creado or {}).get("id", "Pendiente")

    # Responder al usuario con la confirmación requerida
    msg_exito = (
        "🎉 *Ticket registrado con éxito*\n\n"
        "📋 *Resumen de la Solicitud:*\n"
        f"• *Ticket ID:* #{ticket_id}\n"
        f"• *Solicitante:* `{correo_usuario}`\n"
        f"• *Sede:* {sede_seleccionada}\n"
        f"• *Descripción:* {descripcion}\n\n"
        "👨‍💻 Un especialista de TI atenderá tu incidencia a la brevedad.\n\n"
        "Si necesitas reportar otro problema, escribe */start*."
    )
    await send_telegram_message(chat_id, msg_exito)

    # Eliminar el registro de sesión para reiniciar el ciclo en Supabase
    eliminar_sesion(chat_id)
    logger.info(f"[Telegram] Sesión cerrada y eliminada exitosamente para chat_id {chat_id}.")


async def _ejecutar_paso_0_inicio(chat_id: int) -> None:
    """
    Paso 0: Inicializa o reinicia la sesión en 'esperando_correo'
    y envía el saludo de bienvenida pidiendo el correo corporativo.
    """
    upsert_sesion(
        chat_id=chat_id,
        correo_usuario=None,
        paso_actual="esperando_correo",
        datos_temporales={}
    )

    saludo = (
        "👋 *¡Hola! Bienvenido al canal de soporte de HelpStream.*\n\n"
        "Soy el asistente virtual para el registro ágil de tickets de TI.\n\n"
        "Para iniciar, por favor escribe tu *correo corporativo* (ej. `nombre@empresa.com`):"
    )
    await send_telegram_message(chat_id, saludo)
