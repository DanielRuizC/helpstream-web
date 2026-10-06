from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import json
import firebase_admin
from firebase_admin import credentials

# Inicialización de Firebase Admin SDK con credenciales explícitas (HU08)
if not firebase_admin._apps:
    try:
        cred_json = os.environ.get("FIREBASE_CERT")
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("[Firebase Admin] Inicializado exitosamente con FIREBASE_CERT.")
        else:
            print("[Firebase Admin] Variable FIREBASE_CERT no encontrada en el entorno.")
    except Exception as e:
        print(f"[Firebase Admin Error] Error al inicializar Firebase Admin: {e}")

from . import models
from .database import engine
from .routers import tickets, videos, auth, reportes, analytics


# Create database tables
models.Base.metadata.create_all(bind=engine)

from sqlalchemy import text
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tickets ADD COLUMN fecha_creacion DATETIME"))
except Exception:
    pass # La columna ya existe o la tabla no está creada aún

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS palabras_clave VARCHAR"))
except Exception:
    pass

try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS criticidad VARCHAR(50)"))
except Exception:
    pass

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
app.include_router(auth.usuarios_router)
app.include_router(reportes.router)
app.include_router(reportes.dashboard_router)
app.include_router(analytics.router)


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

        # Garantizar existencia de al menos un usuario con rol Jefe de TI (HU20)
        jefe_existente = db.query(models.Usuario).filter(models.Usuario.rol_id == 3).first()
        if not jefe_existente:
            from .auth import get_password_hash
            jefe_default = models.Usuario(
                nombres="Carlos Mendoza",
                apellidos="Jefatura TI",
                correo="jefe@helpstream.com",
                password_hash=get_password_hash("jefe123"),
                rol_id=3,
                activo=True,
                telefono="987654321",
                anexo="101"
            )
            db.add(jefe_default)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()



@app.get("/")
def read_root():
    return {"message": "Welcome to HelpStream API"}
