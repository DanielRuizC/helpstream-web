import os
import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
from ..utils.supabase_client import get_supabase_client
from ..timezone import convertir_a_lima

logger = logging.getLogger("helpstream.telegram")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Expresión regular estándar para validación de formato de correo corporativo
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Sedes corporativas válidas requeridas
SEDES_DISPONIBLES = ["San Isidro", "Chancay", "Ilo", "Pisco", "Coishco"]

# Pisos / Áreas específicos para la sede San Isidro
PISOS_SAN_ISIDRO = [
    "3er piso - Gerencia General",
    "3er piso - Gerencia Flota",
    "3er piso - Gerencia Operaciones",
    "4to piso - Gerencia de Administración y Finanzas",
    "5to piso - Gerencia de Recursos Humanos"
]


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


# ============================================================================
# CONSTRUCTORES DE TECLADOS INTERACTIVOS (INLINE KEYBOARDS)
# ============================================================================

def build_inline_keyboard_menu_principal() -> Dict[str, Any]:
    """
    Construye el menú principal con las 2 opciones de entrada.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "📝 Registrar Ticket", "callback_data": "menu:registrar"}
            ],
            [
                {"text": "🔍 Ver estado de tickets", "callback_data": "menu:estado"}
            ]
        ]
    }


def build_inline_keyboard_sedes() -> Dict[str, Any]:
    """
    Construye el teclado con las sedes exactas:
    San Isidro, Chancay, Ilo, Pisco, Coishco.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🏢 San Isidro", "callback_data": "sede:San Isidro"},
                {"text": "🏭 Chancay", "callback_data": "sede:Chancay"}
            ],
            [
                {"text": "⚓ Ilo", "callback_data": "sede:Ilo"},
                {"text": "📍 Pisco", "callback_data": "sede:Pisco"}
            ],
            [
                {"text": "🐟 Coishco", "callback_data": "sede:Coishco"}
            ]
        ]
    }


def build_inline_keyboard_pisos_san_isidro() -> Dict[str, Any]:
    """
    Construye el teclado condicional de pisos/áreas para la sede San Isidro.
    """
    return {
        "inline_keyboard": [
            [{"text": piso, "callback_data": f"piso:{piso}"}]
            for piso in PISOS_SAN_ISIDRO
        ]
    }


def es_correo_valido(correo: str) -> bool:
    """Valida sintaxis de correo electrónico corporativo."""
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
    paso_actual: str = "menu_principal",
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


def insertar_ticket(
    correo: str,
    descripcion: str,
    sede: str,
    piso: str = "No especificado"
) -> Optional[Dict[str, Any]]:
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
            "piso": (piso or "No especificado").strip(),
            "estado": "Abierto",
            "criticidad": "Medio",
            "fecha_creacion": datetime.utcnow().isoformat(),
            "palabras_clave": "telegram, ticket, soporte"
        }

        res = supabase.table("tickets").insert(ticket_payload).execute()
        logger.info(f"[Supabase] Ticket insertado con éxito para {correo} en sede {sede} ({piso}).")
        return res.data[0] if (res.data and len(res.data) > 0) else ticket_payload
    except Exception as e:
        logger.exception(f"[Supabase] Error al registrar ticket en tickets: {e}")
        return None


def consultar_ultimos_tickets(correo: str, limite: int = 3) -> List[Dict[str, Any]]:
    """
    Consulta los últimos tickets de un usuario en Supabase filtrados por correo_solicitante.
    """
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("tickets")
            .select("id, estado, descripcion, sede, piso, fecha_creacion, comentario_tecnico")
            .eq("correo_solicitante", correo.strip().lower())
            .order("id", desc=True)
            .limit(limite)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"[Supabase] Error al consultar tickets para {correo}: {e}")
        return []


# ============================================================================
# FORMATEO DE TICKETS PARA TELEGRAM (MARKDOWN ENRIQUECIDO)
# ============================================================================

def _sanear_markdown(texto: str) -> str:
    """
    Escapa caracteres especiales de Telegram Markdown v1 (_, *, `, [)
    en texto dinámico para evitar fallos de parseo en la API.
    """
    if not texto:
        return ""
    for char in ["_", "*", "`", "["]:
        texto = texto.replace(char, f"\\{char}")
    return texto


def _formatear_ubicacion_ticket(sede: Optional[str], piso: Optional[str]) -> str:
    """
    Formatea la ubicación combinando sede y piso/área.
    Si el piso es nulo, vacío o 'No especificado', se muestra únicamente la sede.
    Maneja nulos adecuadamente para evitar cadenas extrañas.
    """
    sede_limpia = (sede or "").strip()
    piso_limpio = (piso or "").strip()

    valores_nulos = {"no especificado", "none", "null", "n/a", "-", ""}
    tiene_sede = bool(sede_limpia and sede_limpia.lower() not in valores_nulos)
    tiene_piso = bool(piso_limpio and piso_limpio.lower() not in valores_nulos)

    if tiene_sede and tiene_piso:
        return f"{sede_limpia} | {piso_limpio}"
    elif tiene_sede:
        return sede_limpia
    elif tiene_piso:
        return piso_limpio
    else:
        return "No especificada"


def _formatear_fecha_ticket(fecha_raw: Any) -> str:
    """
    Formatea la fecha de creación del ticket al formato DD/MM/YYYY en hora local (America/Lima).
    """
    if not fecha_raw:
        return "No disponible"
    try:
        if isinstance(fecha_raw, str):
            str_limpio = fecha_raw.strip()
            # Si solo contiene fecha sin hora (YYYY-MM-DD)
            if "T" not in str_limpio and " " not in str_limpio and len(str_limpio) == 10:
                partes = str_limpio.split("-")
                if len(partes) == 3 and len(partes[0]) == 4:
                    return f"{partes[2]}/{partes[1]}/{partes[0]}"

            fecha_iso = str_limpio.replace("Z", "+00:00")
            dt = datetime.fromisoformat(fecha_iso)
        elif isinstance(fecha_raw, datetime):
            dt = fecha_raw
        else:
            return "No disponible"

        dt_lima = convertir_a_lima(dt)
        fecha_obj = dt_lima if dt_lima else dt
        return fecha_obj.strftime("%d/%m/%Y")
    except Exception:
        try:
            partes = str(fecha_raw).split("T")[0].split(" ")[0].split("-")
            if len(partes) == 3 and len(partes[0]) == 4:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            pass
        return "No disponible"


def _formatear_detalle_ticket(descripcion: Optional[str], max_len: int = 100) -> str:
    """
    Limpia y trunca la descripción a un máximo de 100 caracteres.
    """
    if not descripcion or not descripcion.strip():
        return "Sin descripción provista"

    desc_limpia = " ".join(descripcion.strip().split())
    if len(desc_limpia) > max_len:
        return f"{desc_limpia[:max_len].strip()}..."
    return desc_limpia


def _formatear_solucion_ticket(comentario: Optional[str], max_len: int = 100) -> Optional[str]:
    """
    Limpia y trunca el comentario técnico o solución a un máximo de 100 caracteres.
    Retorna None si no hay un comentario válido.
    """
    if not comentario or not isinstance(comentario, str):
        return None

    limpio = " ".join(comentario.strip().split())
    valores_invalidos = {"none", "null", "n/a", "-", "no especificado", "sin comentario", "sin comentarios"}
    if not limpio or limpio.lower() in valores_invalidos:
        return None

    if len(limpio) > max_len:
        return f"{limpio[:max_len].strip()}..."
    return limpio


def _formatear_bloque_ticket(ticket: Dict[str, Any]) -> str:
    """
    Construye el bloque de texto enriquecido en Markdown de Telegram para un ticket.
    Estructura requerida:
    🎫 Ticket #121 — [Resuelto]
    📍 Ubicación: San Isidro | 3er piso - Gerencia General
    📅 Fecha: DD/MM/YYYY
    📝 Detalle: [Descripción truncada a un máximo de 100 caracteres...]
    💡 Solución: [Comentario técnico truncado a 100 caracteres...] (si está resuelto)
    """
    t_id = ticket.get("id", "S/N")
    estado = (ticket.get("estado") or "Abierto").strip()
    ubicacion = _formatear_ubicacion_ticket(ticket.get("sede"), ticket.get("piso"))
    fecha = _formatear_fecha_ticket(ticket.get("fecha_creacion"))
    detalle = _formatear_detalle_ticket(ticket.get("descripcion"), max_len=100)

    estado_seguro = _sanear_markdown(estado)
    ubicacion_segura = _sanear_markdown(ubicacion)
    detalle_seguro = _sanear_markdown(detalle)

    lineas = [
        f"🎫 *Ticket #{t_id}* — [{estado_seguro}]",
        f"📍 *Ubicación:* {ubicacion_segura}",
        f"📅 *Fecha:* {fecha}",
        f"📝 *Detalle:* {detalle_seguro}"
    ]

    # Si el ticket está resuelto y cuenta con solución técnica válida, añadir la línea correspondiente
    if estado.lower() == "resuelto":
        solucion = _formatear_solucion_ticket(ticket.get("comentario_tecnico"), max_len=100)
        if solucion:
            solucion_segura = _sanear_markdown(solucion)
            lineas.append(f"💡 *Solución:* {solucion_segura}")

    return "\n".join(lineas)


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
            logger.debug(f"[Telegram] Update ignorado: {list(update.keys())}")
    except Exception as e:
        logger.exception(f"[Telegram] Error inesperado procesando update {update.get('update_id')}: {e}")


async def _ejecutar_paso_0_inicio(chat_id: int) -> None:
    """
    Requerimiento 1: Modifica el comportamiento de /start.
    Saluda y envía un InlineKeyboardMarkup con dos opciones:
    - Registrar Ticket (menu:registrar)
    - Ver estado de tickets (menu:estado)
    """
    upsert_sesion(
        chat_id=chat_id,
        correo_usuario=None,
        paso_actual="menu_principal",
        datos_temporales={}
    )

    teclado = build_inline_keyboard_menu_principal()
    saludo = (
        "👋 *¡Hola! Bienvenido al canal de soporte de HelpStream.*\n\n"
        "Soy tu asistente virtual de TI. Por favor, selecciona una de las siguientes opciones:"
    )
    await send_telegram_message(chat_id, saludo, reply_markup=teclado)


async def _procesar_mensaje_texto(message: Dict[str, Any]) -> None:
    """Procesa los mensajes de texto entrantes según la máquina de estados."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    texto = (message.get("text") or "").strip()

    if not chat_id:
        return

    # Comando /start: Siempre regresa al menú principal
    if texto.startswith("/start"):
        await _ejecutar_paso_0_inicio(chat_id)
        return

    sesion = obtener_sesion(chat_id)

    # Si no hay sesión previa, mostrar menú principal
    if not sesion:
        await _ejecutar_paso_0_inicio(chat_id)
        return

    paso_actual = sesion.get("paso_actual", "menu_principal")

    # ------------------------------------------------------------------------
    # ESTADO: menu_principal (El usuario escribió texto en vez de pulsar botón)
    # ------------------------------------------------------------------------
    if paso_actual == "menu_principal":
        teclado = build_inline_keyboard_menu_principal()
        msg = "👇 Por favor, presiona uno de los botones para continuar:"
        await send_telegram_message(chat_id, msg, reply_markup=teclado)
        return

    # ------------------------------------------------------------------------
    # FLUJO REGISTRAR - PASO: esperando_correo_registro
    # ------------------------------------------------------------------------
    if paso_actual == "esperando_correo_registro":
        if not es_correo_valido(texto):
            msg_error = (
                "⚠️ *Correo inválido*\n\n"
                "El texto ingresado no tiene un formato válido de correo corporativo.\n"
                "Por favor, asegúrate de ingresar tu correo (ej. `nombre@empresa.com`):"
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
            "Por favor, describe detalladamente el inconveniente técnico o solicitud que presentas:"
        )
        await send_telegram_message(chat_id, msg_pregunta)
        return

    # ------------------------------------------------------------------------
    # FLUJO REGISTRAR - PASO: esperando_descripcion
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_descripcion":
        if len(texto) < 5:
            msg_corta = (
                "⚠️ La descripción es muy breve.\n"
                "Por favor, brinda más detalles sobre el problema:"
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
            "Por favor, selecciona la sede donde ocurre la incidencia:"
        )
        await send_telegram_message(chat_id, msg_sede, reply_markup=teclado)
        return

    # ------------------------------------------------------------------------
    # FLUJO REGISTRAR - PASO: esperando_sede (Texto en lugar de botón)
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_sede":
        teclado = build_inline_keyboard_sedes()
        msg_recordatorio = (
            "⚠️ Por favor, utiliza los botones interactivos para elegir tu sede:\n"
            "• San Isidro\n• Chancay\n• Ilo\n• Pisco\n• Coishco\n\n"
            "O escribe */start* para reiniciar."
        )
        await send_telegram_message(chat_id, msg_recordatorio, reply_markup=teclado)
        return

    # ------------------------------------------------------------------------
    # FLUJO REGISTRAR - PASO: esperando_piso (Texto en lugar de botón)
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_piso":
        teclado = build_inline_keyboard_pisos_san_isidro()
        msg_recordatorio = (
            "⚠️ Por favor, selecciona el piso/área de San Isidro usando los botones inferiores "
            "o escribe */start* para reiniciar:"
        )
        await send_telegram_message(chat_id, msg_recordatorio, reply_markup=teclado)
        return

    # ------------------------------------------------------------------------
    # FLUJO VER ESTADO - PASO: esperando_correo_estado
    # ------------------------------------------------------------------------
    elif paso_actual == "esperando_correo_estado":
        if not es_correo_valido(texto):
            msg_error = (
                "⚠️ *Correo inválido*\n\n"
                "Por favor, ingresa un correo corporativo válido para buscar tus tickets (ej. `nombre@empresa.com`):"
            )
            await send_telegram_message(chat_id, msg_error)
            return

        correo_limpio = texto.lower()
        tickets = consultar_ultimos_tickets(correo_limpio, limite=3)

        if not tickets:
            msg_vacio = (
                "ℹ️ *No tienes tickets registrados*\n\n"
                f"No encontramos tickets asociados al correo `{correo_limpio}`.\n\n"
                "Escribe */start* para volver al menú principal o registrar uno nuevo."
            )
            await send_telegram_message(chat_id, msg_vacio)
        else:
            # Formatear últimos tickets con el bloque de texto enriquecido en Markdown de Telegram
            items_formateados = [_formatear_bloque_ticket(t) for t in tickets]
            texto_tickets = "\n\n".join(items_formateados)
            msg_resultado = (
                f"🔍 *Últimos tickets de:* `{correo_limpio}`\n\n"
                f"{texto_tickets}\n\n"
                "Escribe */start* para volver al menú principal."
            )
            await send_telegram_message(chat_id, msg_resultado)

        # Limpiar la sesión al concluir la consulta
        eliminar_sesion(chat_id)
        return

    else:
        # Estado desconocido -> reiniciar a menú principal
        await _ejecutar_paso_0_inicio(chat_id)


async def _procesar_callback_query(callback: Dict[str, Any]) -> None:
    """
    Procesa las pulsaciones de botones InlineKeyboardMarkup:
    - Menú Principal: menu:registrar, menu:estado
    - Selección de Sede: sede:<nombre>
    - Selección de Piso: piso:<nombre>
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

    # ========================================================================
    # EVENTOS DE MENÚ PRINCIPAL
    # ========================================================================
    if raw_data == "menu:registrar":
        upsert_sesion(
            chat_id=chat_id,
            correo_usuario=None,
            paso_actual="esperando_correo_registro",
            datos_temporales={}
        )
        msg = (
            "📝 *Registro de Ticket*\n\n"
            "Por favor, ingresa tu *correo corporativo* (ej. `nombre@empresa.com`):"
        )
        await send_telegram_message(chat_id, msg)
        return

    elif raw_data == "menu:estado":
        upsert_sesion(
            chat_id=chat_id,
            correo_usuario=None,
            paso_actual="esperando_correo_estado",
            datos_temporales={}
        )
        msg = (
            "🔍 *Consulta de Estado de Tickets*\n\n"
            "Por favor, ingresa tu *correo corporativo* para consultar tus solicitudes (ej. `nombre@empresa.com`):"
        )
        await send_telegram_message(chat_id, msg)
        return

    # ========================================================================
    # EVENTOS DE SELECCIÓN DE SEDE
    # ========================================================================
    elif raw_data.startswith("sede:"):
        sede_seleccionada = raw_data.replace("sede:", "").strip()

        if sede_seleccionada not in SEDES_DISPONIBLES:
            logger.warning(f"[Telegram] Sede no reconocida recibida: {sede_seleccionada}")
            return

        sesion = obtener_sesion(chat_id)
        if not sesion or sesion.get("paso_actual") != "esperando_sede":
            msg_expirado = (
                "⚠️ Esta solicitud ya fue completada o la sesión ha expirado.\n"
                "Escribe */start* para ir al menú principal."
            )
            await send_telegram_message(chat_id, msg_expirado)
            return

        datos_temporales = sesion.get("datos_temporales") or {}
        datos_temporales["sede"] = sede_seleccionada
        correo_usuario = sesion.get("correo_usuario") or "usuario@helpstream.com"
        descripcion = datos_temporales.get("descripcion", "Sin descripción provista")

        # --------------------------------------------------------------------
        # LÓGICA CONDICIONAL DE PISOS:
        # SI es San Isidro -> Preguntar piso con teclado
        # SI es distinta -> Insertar directamente con piso 'No especificado'
        # --------------------------------------------------------------------
        if sede_seleccionada == "San Isidro":
            actualizar_sesion(chat_id, {
                "datos_temporales": datos_temporales,
                "paso_actual": "esperando_piso"
            })
            teclado_pisos = build_inline_keyboard_pisos_san_isidro()
            msg_piso = (
                "🏢 *Sede San Isidro seleccionada*\n\n"
                "Por favor, selecciona el piso o gerencia correspondiente:"
            )
            await send_telegram_message(chat_id, msg_piso, reply_markup=teclado_pisos)
            return

        else:
            # Sede distinta a San Isidro: Registrar ticket con piso 'No especificado'
            ticket_creado = insertar_ticket(
                correo=correo_usuario,
                descripcion=descripcion,
                sede=sede_seleccionada,
                piso="No especificado"
            )
            ticket_id = (ticket_creado or {}).get("id", "Generado")

            msg_exito = (
                "🎉 *Ticket registrado con éxito*\n\n"
                "📋 *Resumen de la Solicitud:*\n"
                f"• *Ticket ID:* #{ticket_id}\n"
                f"• *Solicitante:* `{correo_usuario}`\n"
                f"• *Sede:* {sede_seleccionada}\n"
                f"• *Área/Piso:* No especificado\n"
                f"• *Descripción:* {descripcion}\n\n"
                "👨‍💻 Un especialista de TI atenderá tu incidencia a la brevedad.\n\n"
                "Escribe */start* para volver al menú principal."
            )
            await send_telegram_message(chat_id, msg_exito)
            eliminar_sesion(chat_id)
            logger.info(f"[Telegram] Ticket creado para chat_id {chat_id} en sede {sede_seleccionada}. Sesión cerrada.")
            return

    # ========================================================================
    # EVENTOS DE SELECCIÓN DE PISO (SAN ISIDRO)
    # ========================================================================
    elif raw_data.startswith("piso:"):
        piso_seleccionado = raw_data.replace("piso:", "").strip()

        sesion = obtener_sesion(chat_id)
        if not sesion or sesion.get("paso_actual") != "esperando_piso":
            msg_expirado = (
                "⚠️ Esta solicitud ya fue completada o la sesión ha expirado.\n"
                "Escribe */start* para ir al menú principal."
            )
            await send_telegram_message(chat_id, msg_expirado)
            return

        correo_usuario = sesion.get("correo_usuario") or "usuario@helpstream.com"
        datos_temporales = sesion.get("datos_temporales") or {}
        descripcion = datos_temporales.get("descripcion", "Sin descripción provista")
        sede = datos_temporales.get("sede", "San Isidro")

        # Insertar ticket con sede y piso seleccionados
        ticket_creado = insertar_ticket(
            correo=correo_usuario,
            descripcion=descripcion,
            sede=sede,
            piso=piso_seleccionado
        )
        ticket_id = (ticket_creado or {}).get("id", "Generado")

        msg_exito = (
            "🎉 *Ticket registrado con éxito*\n\n"
            "📋 *Resumen de la Solicitud:*\n"
            f"• *Ticket ID:* #{ticket_id}\n"
            f"• *Solicitante:* `{correo_usuario}`\n"
            f"• *Sede:* {sede}\n"
            f"• *Área/Piso:* {piso_seleccionado}\n"
            f"• *Descripción:* {descripcion}\n\n"
            "👨‍💻 Un especialista de TI atenderá tu incidencia a la brevedad.\n\n"
            "Escribe */start* para volver al menú principal."
        )
        await send_telegram_message(chat_id, msg_exito)
        eliminar_sesion(chat_id)
        logger.info(f"[Telegram] Ticket creado para chat_id {chat_id} en San Isidro ({piso_seleccionado}). Sesión cerrada.")
        return

    else:
        logger.debug(f"[Telegram] Callback data no reconocida: {raw_data}")
