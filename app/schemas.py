from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TicketBase(BaseModel):
    usuario_id: int
    descripcion: str = Field(..., max_length=250)

class TicketCreate(TicketBase):
    pass

class TicketUpdateEstado(BaseModel):
    estado: str
    comentario_tecnico: Optional[str] = None

class TicketResponse(TicketBase):
    id: int
    estado: str
    comentario_tecnico: Optional[str] = None
    evidencia_url: Optional[str] = None
    criticidad: Optional[str] = "Medio"
    fecha_creacion: Optional[datetime] = None
    palabras_clave: List[str] = []

    class Config:
        from_attributes = True
        orm_mode = True

class VideoCreate(BaseModel):
    titulo: str
    descripcion: str
    url_video: str
    tags: str

class VideoRespuesta(BaseModel):
    id: int
    titulo: str
    descripcion: str
    url_video: str
    tags: str
    fecha_subida: datetime

    class Config:
        from_attributes = True
        orm_mode = True
