import os
import string
import logging
import json
from typing import List
from dotenv import load_dotenv
from google import genai
from groq import AsyncGroq

load_dotenv()

# Instancia del cliente principal Google GenAI
try:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
except Exception:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or "AIzaSyDummyKeyForInitialization")

# Instancia del cliente de respaldo Groq (Fallback de alta disponibilidad)
try:
    groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    groq_client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY") or "gsk_dummy_key_for_initialization")

logger = logging.getLogger(__name__)


async def analizar_ticket_ia(descripcion: str) -> dict:
    """
    Analiza la descripción del ticket utilizando Gemini AI (gemini-3.8-flash).
    Si Gemini falla (error 503, cuota, etc.), ejecuta el fallback con Groq (llama3-8b-8192).
    Si ambos fallan, retorna como respaldo seguro: {"palabras_clave": [], "criticidad": "Media"}.
    """
    if not descripcion or not descripcion.strip():
        return {"palabras_clave": [], "criticidad": "Media"}

    try:
        global client
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and getattr(client, "_api_client", None) and getattr(client._api_client, "api_key", None) != api_key:
            client = genai.Client(api_key=api_key)

        prompt = (
            f"Eres un analista de soporte técnico TI. Analiza esta descripción y extrae de 2 a 5 palabras clave técnicas. "
            f"Además, determina el nivel de criticidad (Baja, Media, Alta, Crítica) según la urgencia "
            f"(ej. caída de red = Crítica, atasco de papel = Baja). "
            f"Devuelve ÚNICAMENTE un objeto JSON válido con la estructura: "
            f'{{"palabras_clave": ["..."], "criticidad": "..."}} sin bloques de código markdown. '
            f"Descripción: {descripcion.strip()}"
        )
        response = await client.aio.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt
        )

        if not response or not response.text:
            raise ValueError("Respuesta vacía de Gemini")

        raw_text = response.text.strip()
        cleaned_text = raw_text.replace("```json", "").replace("```", "").replace("`", "").strip()
        data = json.loads(cleaned_text)

        palabras = data.get("palabras_clave", [])
        if not isinstance(palabras, list):
            palabras = [str(palabras)]
        criticidad = data.get("criticidad", "Media")

        return {
            "palabras_clave": [str(p).strip().lower() for p in palabras if str(p).strip()],
            "criticidad": str(criticidad).strip().capitalize()
        }
    except Exception as e_gemini:
        logger.warning(f"[Gemini AI Fallback Triggered] Falla en Gemini ({e_gemini}). Activando fallback Groq Llama3...")
        try:
            global groq_client
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key and getattr(groq_client, "api_key", None) != groq_key:
                groq_client = AsyncGroq(api_key=groq_key)

            fallback_response = await groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un analista de soporte técnico TI. Analiza esta descripción y extrae de 2 a 5 palabras clave técnicas. "
                            "Además, determina el nivel de criticidad (Baja, Media, Alta, Crítica). "
                            "Devuelve ÚNICAMENTE un objeto JSON válido con la estructura: "
                            "{\"palabras_clave\": [\"...\"], \"criticidad\": \"...\"} sin bloques de código markdown ni texto adicional."
                        )
                    },
                    {"role": "user", "content": descripcion}
                ],
                temperature=0.1
            )

            raw_fallback = fallback_response.choices[0].message.content.strip()
            cleaned_fallback = raw_fallback.replace("```json", "").replace("```", "").replace("`", "").strip()
            data_fallback = json.loads(cleaned_fallback)

            palabras = data_fallback.get("palabras_clave", [])
            if not isinstance(palabras, list):
                palabras = [str(palabras)]
            criticidad = data_fallback.get("criticidad", "Media")

            return {
                "palabras_clave": [str(p).strip().lower() for p in palabras if str(p).strip()],
                "criticidad": str(criticidad).strip().capitalize()
            }
        except Exception as e_groq:
            logger.error(f"[Groq AI Fallback Error] Falló el servicio Groq de contingencia: {e_groq}")
            return {"palabras_clave": [], "criticidad": "Media"}


async def extraer_palabras_clave_ia(descripcion: str) -> list[str]:
    """Función de compatibilidad retroactiva para extracción exclusiva de palabras clave."""
    res = await analizar_ticket_ia(descripcion)
    return res.get("palabras_clave", [])


def analizar_ticket_heuristico(texto: str) -> dict:
    """Función heurística síncrona de respaldo para tickets legacy."""
    texto_lower = texto.lower()
    
    # Extraer palabras clave (lógica heurística de respaldo)
    for p in string.punctuation:
        texto_lower = texto_lower.replace(p, "")
    stopwords = {"el", "la", "que", "de", "no", "se", "mi", "a", "en", "y", "los", "las", "un", "una", "por", "con", "para"}
    palabras = [palabra for palabra in texto_lower.split() if palabra not in stopwords]
    
    # Determinar criticidad (Simulador de respaldo)
    palabras_criticas = {"fuga", "caida", "servidor", "red", "planta", "urgente", "fuego", "corto", "caldera", "apago", "bloqueo", "total"}
    palabras_bajas = {"impresora", "papel", "lento", "correo", "clave", "duda"}
    
    criticidad = "Media"
    for p in palabras:
        if p in palabras_criticas:
            criticidad = "Crítica"
            break
        elif p in palabras_bajas:
            criticidad = "Baja"
            
    return {
        "palabras_clave": palabras,
        "criticidad": criticidad
    }
