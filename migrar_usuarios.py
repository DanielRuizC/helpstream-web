import sys
from sqlalchemy import text
from app.database import engine

def migrar_usuarios():
    print("Conectando y aplicando migraciones a la tabla usuarios...")
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telefono VARCHAR(50);"))
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS anexo VARCHAR(10);"))
            conn.commit()
        print("[+] Migración completada exitosamente: columnas 'telefono' y 'anexo' agregadas a 'usuarios'.")
    except Exception as e:
        print(f"[-] Error al ejecutar migración: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrar_usuarios()
