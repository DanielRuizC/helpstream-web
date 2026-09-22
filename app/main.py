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


@app.get("/")
def read_root():
    return {"message": "Welcome to HelpStream API"}
