from fastapi import APIRouter, Depends, Form, File, UploadFile
import os
import uuid
import shutil
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from .. import models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/videos",
    tags=["Gestión de Conocimiento TI"]
)

@router.post("", response_model=schemas.VideoRespuesta)
def create_video(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    tags: str = Form(...),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Convertir tags a minúsculas para optimizar búsqueda predictiva
    tags_lower = tags.lower() if tags else ""
    
    # Generar un nombre de archivo único para evitar sobreescrituras
    ext = os.path.splitext(video_file.filename)[1] if video_file.filename else ".mp4"
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join("static", "videos", unique_filename)
    
    # Guardar físicamente el archivo
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)
        
    url_video_relativa = f"/static/videos/{unique_filename}"
    
    db_video = models.VideoTutorial(
        titulo=titulo,
        descripcion=descripcion,
        url_video=url_video_relativa,
        tags=tags_lower
    )
    
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

@router.get("", response_model=List[schemas.VideoRespuesta])
def get_videos(skip: int = 0, limit: int = 100, tags: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.VideoTutorial)
    
    if tags:
        search_tags = [t.strip().lower() for t in tags.split(",")]
        conditions = [models.VideoTutorial.tags.ilike(f"%{t}%") for t in search_tags]
        query = query.filter(or_(*conditions))
        
    videos = query.offset(skip).limit(limit).all()
    return videos
