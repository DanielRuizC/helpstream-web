import string
from typing import List

def analizar_ticket_ia(texto: str) -> dict:
    texto_lower = texto.lower()
    
    # Extraer palabras clave (lógica reutilizada de HU03)
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
