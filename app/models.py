# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, Text, DateTime
# pyrefly: ignore [missing-import]
from .database import Base
from datetime import datetime

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