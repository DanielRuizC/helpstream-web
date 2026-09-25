from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ==========================================
# ESQUEMAS RBAC (Control de Acceso Basado en Roles)
# Niveles: usuario_planta, analista_ti, jefe_ti
# ==========================================

# --- Rol ---
class RolBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class RolCreate(RolBase):
    pass

class RolResponse(RolBase):
    id: int

    class Config:
        from_attributes = True
        orm_mode = True

# --- Usuario ---
class UsuarioBase(BaseModel):
    nombres: str
    apellidos: Optional[str] = None
    correo: str
    rol_id: int
    activo: bool = True

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioRegistro(BaseModel):
    nombre: str
    correo: str
    password: str
    rol_id: int

class UsuarioUpdate(BaseModel):
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    correo: Optional[str] = None
    rol_id: Optional[int] = None
    activo: Optional[bool] = None

class UsuarioLogin(BaseModel):
    correo: str
    password: str

class UsuarioResponse(BaseModel):
    id: int
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    correo: str
    rol_id: int
    activo: bool = True

    class Config:
        from_attributes = True
        orm_mode = True

# --- Tokens JWT ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    rol_id: Optional[int] = None
    correo: Optional[str] = None


# ==========================================
# ESQUEMAS DE TICKETS Y VIDEOS
# ==========================================

class TicketBase(BaseModel):
    usuario_id: int
    descripcion: str = Field(..., max_length=250)
    correo_solicitante: Optional[str] = None
    sede: Optional[str] = None
    piso: Optional[str] = None

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
