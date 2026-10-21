#!/usr/bin/env python3
"""
HelpStream - Script de Configuración del Webhook de Telegram
============================================================
Este script independiente permite registrar, verificar o eliminar la URL
del webhook en la API de Telegram para el despliegue en Render.

Uso:
    python set_webhook.py https://tu-app.onrender.com/api/telegram/webhook
    o simplemente:
    python set_webhook.py  (tomará la URL desde .env o la solicitará por consola)
"""

import os
import sys
import argparse
import httpx
from dotenv import load_dotenv

# Cargar variables de entorno desde .env local si existe
load_dotenv()


def obtener_bot_token() -> str:
    """Obtiene y valida el token del bot de Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\n❌ ERROR: La variable de entorno 'TELEGRAM_BOT_TOKEN' no está configurada.")
        print("   Configúrala en tu archivo .env o en el Dashboard de Render:")
        print("   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz\n")
        sys.exit(1)
    return token


def configurar_webhook(bot_token: str, webhook_url: str) -> bool:
    """
    Envía la petición a la API de Telegram para registrar la URL del webhook.
    """
    if not webhook_url.startswith("https://"):
        print(f"\n⚠️  ADVERTENCIA: Telegram exige HTTPS para webhooks. La URL ingresada es: {webhook_url}")
        print("   Por favor verifica que la URL comience con https://")

    endpoint = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    payload = {
        "url": webhook_url,
        "drop_pending_updates": True,  # Descarta actualizaciones acumuladas previas para evitar colapsos
        "allowed_updates": ["message", "callback_query"]
    }

    print(f"\n🚀 Enviando petición a Telegram para registrar Webhook...")
    print(f"   URL objetivo: {webhook_url}")

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(endpoint, json=payload)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                print("✅ ¡Webhook configurado con ÉXITO en Telegram!")
                print(f"   Descripción: {data.get('description', 'OK')}")
                return True
            else:
                print(f"❌ Falló la configuración del Webhook (HTTP {response.status_code}):")
                print(f"   Detalle: {data.get('description', response.text)}")
                return False

    except httpx.RequestError as exc:
        print(f"❌ Error de conexión al comunicarse con Telegram: {exc}")
        return False
    except Exception as exc:
        print(f"❌ Error inesperado: {exc}")
        return False


def obtener_info_webhook(bot_token: str) -> None:
    """Consulta el estado actual del webhook registrado en Telegram."""
    endpoint = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(endpoint)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                result = data.get("result", {})
                print("\n📊 ESTADO ACTUAL DEL WEBHOOK EN TELEGRAM:")
                print(f"   • URL Registrada:      {result.get('url') or '(Ninguna / Modo Polling)'}")
                print(f"   • Actualizaciones pendientes: {result.get('pending_update_count', 0)}")
                print(f"   • IP personalizada:    {result.get('ip_address', 'N/A')}")
                if result.get("last_error_date"):
                    print(f"   • Último error:        {result.get('last_error_message')} (Fecha: {result.get('last_error_date')})")
                else:
                    print(f"   • Estado de salud:     Óptimo (Sin errores registrados)")
            else:
                print(f"⚠️ No se pudo obtener la información: {data.get('description', response.text)}")

    except Exception as exc:
        print(f"⚠️ No se pudo consultar getWebhookInfo: {exc}")


def eliminar_webhook(bot_token: str) -> None:
    """Elimina el webhook registrado para volver al modo polling o mantenimiento."""
    endpoint = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, json={"drop_pending_updates": True})
            data = response.json()
            if data.get("ok"):
                print("🗑️ Webhook eliminado correctamente de Telegram.")
            else:
                print(f"❌ No se pudo eliminar el webhook: {data.get('description')}")
    except Exception as exc:
        print(f"❌ Error eliminando webhook: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="Script para configurar el Webhook de Telegram para HelpStream en Render."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="URL completa del webhook (ej: https://mi-backend.onrender.com/api/telegram/webhook)"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Solo consultar el estado actual del webhook en Telegram"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Eliminar el webhook activo en Telegram"
    )

    args = parser.parse_args()
    bot_token = obtener_bot_token()

    if args.info:
        obtener_info_webhook(bot_token)
        return

    if args.delete:
        eliminar_webhook(bot_token)
        obtener_info_webhook(bot_token)
        return

    webhook_url = args.url or os.environ.get("WEBHOOK_URL")

    # Si no se pasó por argumento ni por variable, solicitar por consola
    if not webhook_url:
        print("\n🔧 CONFIGURACIÓN DE WEBHOOK TELEGRAM - HELPSTREAM")
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        sugerencia = f"{render_url}/api/telegram/webhook" if render_url else "https://helpstream-backend.onrender.com/api/telegram/webhook"
        print(f"Ejemplo sugerido: {sugerencia}")
        ingreso = input(f"Ingresa la URL pública de tu webhook en Render [{sugerencia}]: ").strip()
        webhook_url = ingreso if ingreso else sugerencia

    # Ejecutar configuración y mostrar diagnóstico posterior
    exito = configurar_webhook(bot_token, webhook_url)
    if exito:
        obtener_info_webhook(bot_token)


if __name__ == "__main__":
    main()
