from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
import os
import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from .. import models, schemas
from ..database import get_db
from ..utils.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/videos",
    tags=["Gestión de Conocimiento TI"]
)

BUCKET_NAME = "videos_tutoriales"


def generar_url_firmada(storage, ruta_archivo: str, expires_in: int = 3600) -> str:
    """
    Genera una URL firmada temporal de Supabase Storage para el archivo especificado.
    Si la ruta ya es una URL externa o falla la generación, retorna la ruta original de forma segura.
    """
    if not ruta_archivo:
        return ""
    
    # Si ya es una URL externa (no de Supabase Storage privado), devolverla
    if ruta_archivo.startswith(("http://", "https://")) and "supabase.co" not in ruta_archivo:
        return ruta_archivo

    try:
        # Extraer nombre base si proviene de rutas locales legacy (ej. /static/videos/...)
        clean_path = os.path.basename(ruta_archivo) if "/static/videos/" in ruta_archivo else ruta_archivo
        signed_resp = storage.from_(BUCKET_NAME).create_signed_url(clean_path, expires_in)
        signed_url = signed_resp.get("signedURL") or signed_resp.get("signedUrl")
        return signed_url or ruta_archivo
    except Exception as e:
        logger.warning(f"[Supabase Storage] No se pudo generar URL firmada para {ruta_archivo}: {e}")
        return ruta_archivo


@router.post("", response_model=schemas.VideoRespuesta)
@router.post("/", response_model=schemas.VideoRespuesta, include_in_schema=False)
async def create_video(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    tags: str = Form(...),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Convertir tags a minúsculas para optimizar búsqueda predictiva
    tags_lower = tags.lower() if tags else ""

    # Generar un nombre de archivo único para evitar colisiones en Supabase Storage
    ext = os.path.splitext(video_file.filename)[1] if video_file.filename else ".mp4"
    if not ext:
        ext = ".mp4"
    unique_filename = f"{uuid.uuid4()}{ext}"

    # Leer los bytes del archivo multimedia recibido
    try:
        file_bytes = await video_file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error al leer el archivo de video: {str(e)}"
        )

    # Subir directamente al bucket 'videos_tutoriales' de Supabase Storage
    client = get_supabase_client()
    storage = client.storage

    content_type = video_file.content_type or "video/mp4"
    file_options = {"content-type": content_type}

    try:
        storage.from_(BUCKET_NAME).upload(
            path=unique_filename,
            file=file_bytes,
            file_options=file_options
        )
    except Exception as e:
        logger.error(f"[Supabase Storage Error] Error al subir video a bucket {BUCKET_NAME}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir el video a Supabase Storage: {str(e)}"
        )

    ruta_archivo = unique_filename

    # Registrar el video en la base de datos con la ruta del archivo en Storage
    db_video = models.VideoTutorial(
        titulo=titulo,
        descripcion=descripcion,
        url_video=ruta_archivo,
        tags=tags_lower
    )

    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    # Generar URL temporal firmada válida por 1 hora (3600 segundos) para la respuesta
    url_firmada = generar_url_firmada(storage, ruta_archivo, 3600)

    return schemas.VideoRespuesta(
        id=db_video.id,
        titulo=db_video.titulo,
        descripcion=db_video.descripcion,
        url_video=url_firmada,
        tags=db_video.tags,
        fecha_subida=db_video.fecha_subida
    )


@router.get("", response_model=List[schemas.VideoRespuesta])
@router.get("/", response_model=List[schemas.VideoRespuesta], include_in_schema=False)
def get_videos(
    skip: int = 0,
    limit: int = 100,
    tags: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.VideoTutorial)

    if tags:
        search_tags = [t.strip().lower() for t in tags.split(",")]
        conditions = [models.VideoTutorial.tags.ilike(f"%{t}%") for t in search_tags]
        query = query.filter(or_(*conditions))

    videos = query.offset(skip).limit(limit).all()

    client = get_supabase_client()
    storage = client.storage

    resultado: List[schemas.VideoRespuesta] = []
    for video in videos:
        url_firmada = generar_url_firmada(storage, video.url_video, 3600)
        resultado.append(
            schemas.VideoRespuesta(
                id=video.id,
                titulo=video.titulo,
                descripcion=video.descripcion,
                url_video=url_firmada,
                tags=video.tags,
                fecha_subida=video.fecha_subida
            )
        )

    return resultado


@router.get("/{video_id}", response_model=schemas.VideoRespuesta)
def get_video_by_id(video_id: int, db: Session = Depends(get_db)):
    video = db.query(models.VideoTutorial).filter(models.VideoTutorial.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video tutorial no encontrado")

    client = get_supabase_client()
    storage = client.storage
    url_firmada = generar_url_firmada(storage, video.url_video, 3600)

    return schemas.VideoRespuesta(
        id=video.id,
        titulo=video.titulo,
        descripcion=video.descripcion,
        url_video=url_firmada,
        tags=video.tags,
        fecha_subida=video.fecha_subida
    )
