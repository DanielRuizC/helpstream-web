import os
import string
import logging
from typing import List
import google.generativeai as genai

# Configuración del Servicio de IA con Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)


async def extraer_palabras_clave_ia(descripcion: str) -> list[str]:
    """
    Función auxiliar asíncrona que extrae entre 2 y 5 palabras clave técnicas
    principales de la descripción del problema utilizando Google Gemini AI (gemini-1.5-flash).
    En caso de error de la API, captura la excepción y retorna una lista vacía.
    """
    if not descripcion or not descripcion.strip():
        return []

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Eres un analista de soporte técnico TI. Extrae entre 2 y 5 palabras clave técnicas principales "
            f"de esta descripción de problema. Devuelve únicamente las palabras clave separadas por comas, "
            f"sin texto adicional, sin viñetas y en minúsculas. Ignora verbos comunes, pronombres y conectores. "
            f"Descripción: {descripcion.strip()}"
        )
        response = await model.generate_content_async(prompt)
        
        if not response or not response.text:
            return []

        raw_text = response.text.strip()
        # Limpieza de saltos de línea, viñetas o caracteres adicionales
        cleaned_text = raw_text.replace("\n", ",").replace("*", "").replace("-", "")
        palabras = [p.strip().lower() for p in cleaned_text.split(",") if p.strip()]
        return palabras
    except Exception as e:
        logger.error(f"[Gemini AI Error] Error al extraer palabras clave: {e}")
        return []


def analizar_ticket_ia(texto: str) -> dict:
    texto_lower = texto.lower()
    
    # Extraer palabras clave (lógica heurística de respaldo)
    for p in string.punctuation:
        texto_lower = texto_lower.replace(p, "")
    stopwords = {"el", "la", "que", "de", "no", "se", "mi", "a", "en", "y", "los", "las", "un", "una", "por", "con", "para"}
    palabras = [palabra for palabra in texto_lower.split() if palabra not in stopwords]
    
    # Determinar criticidad (Simulador IA de HU06)
    palabras_criticas = {"fuga", "caida", "servidor", "red", "planta", "urgente", "fuego", "corto", "caldera", "apago", "bloqueo", "total"}
    palabras_bajas = {"impresora", "papel", "lento", "correo", "clave", "duda"}
    
    criticidad = "Medio"
    for p in palabras:
        if p in palabras_criticas:
            criticidad = "Crítico"
            break  # Si es crítico, ya no buscamos más
        elif p in palabras_bajas:
            criticidad = "Bajo"
            
    return {
        "palabras_clave": palabras,
        "criticidad": criticidad
    }
