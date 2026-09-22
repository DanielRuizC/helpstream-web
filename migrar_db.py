"""
Script temporal para la migración inicial de la base de datos a PostgreSQL / Supabase.
Crea todas las tablas definidas en los modelos de SQLAlchemy.
"""
import sys

try:
    from app.database import engine, Base
    import app.models  # Importar modelos para que se registren en Base.metadata
except ValueError as e:
    print(f"\n[!] Error de configuración: {e}\n")
    sys.exit(1)
except Exception as e:
    print(f"\n[!] Error al inicializar conexión: {e}\n")
    sys.exit(1)

def migrar():
    print("\n=======================================================")
    print("  HelpStream - Migración Inicial a PostgreSQL (Supabase)")
    print("=======================================================")
    print("[*] Conectando a la base de datos y creando tablas...")
    
    try:
        Base.metadata.create_all(bind=engine)
        print("[+] ¡Migración completada exitosamente!")
        print("[*] Tablas registradas y creadas:")
        for table_name in Base.metadata.tables.keys():
            print(f"    - {table_name}")
        print("=======================================================\n")
    except Exception as e:
        print(f"\n[-] Error al ejecutar la migración: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    migrar()
