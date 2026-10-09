"""
Script para normalizar los valores del campo criticidad en la tabla tickets de PostgreSQL.
Regla de normalización:
- Inicia con 'Alt' -> 'Alto'
- Inicia con 'Med' -> 'Medio'
- Inicia con 'Baj' -> 'Bajo'
- Inicia con 'Crític' o 'Critic' -> 'Crítico'
"""
import sys
from app.database import SessionLocal
from app.models import Ticket

def normalizar_valor(crit: str) -> str:
    if not crit:
        return "Medio"
    crit_str = str(crit).strip()
    crit_lower = crit_str.lower()
    
    if crit_lower.startswith("alt"):
        return "Alto"
    elif crit_lower.startswith("med"):
        return "Medio"
    elif crit_lower.startswith("baj"):
        return "Bajo"
    elif crit_lower.startswith("crític") or crit_lower.startswith("critic") or crit_lower.startswith("cr"):
        return "Crítico"
    return "Medio"

def normalizar_tickets():
    print("==================================================")
    print("  HelpStream - Normalización de Criticidad en BD")
    print("==================================================")
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).all()
        print(f"[*] Total de tickets encontrados: {len(tickets)}")
        
        actualizados = 0
        for t in tickets:
            valor_actual = t.criticidad
            valor_nuevo = normalizar_valor(valor_actual)
            if valor_actual != valor_nuevo:
                print(f"  - Ticket #{t.id}: '{valor_actual}' -> '{valor_nuevo}'")
                t.criticidad = valor_nuevo
                actualizados += 1
                
        db.commit()
        print(f"[+] Actualización completada: {actualizados} tickets modificados.")
        
        # Validación de valores únicos restantes
        unicos = [row[0] for row in db.query(Ticket.criticidad).distinct().all()]
        print(f"[*] Valores únicos finales en BD: {unicos}")
        print("==================================================")
    except Exception as e:
        db.rollback()
        print(f"[-] Error al normalizar tickets: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    normalizar_tickets()
