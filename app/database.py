import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Cargar variables de entorno desde el archivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or DATABASE_URL.strip() == "" or DATABASE_URL == "PEGAR_AQUI_LA_CADENA":
    raise ValueError(
        "ERROR: La variable de entorno 'DATABASE_URL' no está configurada o contiene el valor por defecto. "
        "Por favor, define la cadena de conexión a PostgreSQL/Supabase en el archivo .env."
    )

# Asegurar compatibilidad si la URL inicia con postgres:// (requerido por SQLAlchemy)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URL = DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

