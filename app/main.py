# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from . import models
from .database import engine
from .routers import tickets, videos, auth


# Create database tables
models.Base.metadata.create_all(bind=engine)

from sqlalchemy import text
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tickets ADD COLUMN fecha_creacion DATETIME"))
except Exception:
    pass # La columna ya existe o la tabla no está creada aún

app = FastAPI(title="HelpStream Backend")

os.makedirs("static/videos", exist_ok=True)
os.makedirs("static/evidencias", exist_ok=True)
app.mount("/portal_web", StaticFiles(directory="portal_web", html=True), name="portal")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router)
app.include_router(videos.router)
app.include_router(auth.router)


@app.on_event("startup")
def inicializar_roles_default():
    """Garantiza la existencia de los roles predefinidos en Supabase/PostgreSQL."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        roles_default = [
            (1, "usuario_planta", "Usuario final de planta"),
            (2, "analista_ti", "Analista de Soporte TI"),
            (3, "jefe_ti", "Jefe del Área de TI"),
        ]
        for rol_id, nombre, desc in roles_default:
            existe = db.query(models.Rol).filter(models.Rol.id == rol_id).first()
            if not existe:
                db.add(models.Rol(id=rol_id, nombre=nombre, descripcion=desc))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "Welcome to HelpStream API"}
