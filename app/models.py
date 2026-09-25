# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
# pyrefly: ignore [missing-import]
from .database import Base
from datetime import datetime

# ==========================================
# MODELOS RBAC (Control de Acceso Basado en Roles)
# Niveles: usuario_planta, analista_ti, jefe_ti
# ==========================================

class Rol(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)  # Ej: usuario_planta, analista_ti, jefe_ti
    descripcion = Column(String, nullable=True)

    # Relación bidireccional con Usuario
    usuarios = relationship("Usuario", back_populates="rol")

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombres = Column(String)
    apellidos = Column(String)
    correo = Column(String, unique=True, index=True)
    password_hash = Column(String)
    rol_id = Column(Integer, ForeignKey("roles.id"))
    activo = Column(Boolean, default=True)
    telefono = Column(String, nullable=True)
    anexo = Column(String, nullable=True)

    # Relación bidireccional con Rol
    rol = relationship("Rol", back_populates="usuarios")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, index=True)
    descripcion = Column(String(250))
    estado = Column(String, default="Abierto")
    comentario_tecnico = Column(Text, nullable=True)
    evidencia_url = Column(String, nullable=True)
    criticidad = Column(String, default="Medio")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    correo_solicitante = Column(String, nullable=True)
    sede = Column(String, nullable=True)
    piso = Column(String, nullable=True)

class VideoTutorial(Base):
    __tablename__ = "videos_tutoriales"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, index=True)
    descripcion = Column(String)
    # Para el MVP podemos usar una URL web o la ruta local de un archivo .mp4
    url_video = Column(String) 
    # Aquí guardamos los tags de la HU13, ej: "caldera, fuga, presion, agua"
    tags = Column(String, index=True) 
    fecha_subida = Column(DateTime, default=datetime.utcnow)