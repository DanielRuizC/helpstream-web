from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
import os
import uuid
import logging
import unicodedata
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
STOPWORDS_TAGS = {"de", "la", "el", "en", "y", "a", "un", "una", "por", "con", "para", "del", "los", "las", "al"}


def normalizar_tag(texto: str) -> str:
    """Elimina acentos y normaliza a minúsculas para comparaciones semánticas tolerantes."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def extraer_conjunto_tags(tags_str: Optional[str]) -> set[str]:
    """
    Extrae y normaliza un conjunto de tags tanto a nivel de frase completa
    como a nivel de palabras individuales representativas, permitiendo calcular
    la intersección precisa entre tags de tickets y de videos tutoriales.
    """
    if not tags_str:
        return set()

    tags_set = set()
    frases = [t.strip() for t in tags_str.split(",") if t.strip()]
    for f in frases:
        norm_f = normalizar_tag(f)
        if norm_f:
            tags_set.add(norm_f)
            palabras = [normalizar_tag(p) for p in f.split()]
            for p in palabras:
                if p and p not in STOPWORDS_TAGS and len(p) > 2:
                    tags_set.add(p)

    return tags_set


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
        tags=tags_lower,
        reproducciones=0,
        casos_resueltos=0
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
        fecha_subida=db_video.fecha_subida,
        reproducciones=getattr(db_video, "reproducciones", 0) or 0,
        casos_resueltos=getattr(db_video, "casos_resueltos", 0) or 0
    )


@router.get("", response_model=List[schemas.VideoRespuesta])
@router.get("/", response_model=List[schemas.VideoRespuesta], include_in_schema=False)
def get_videos(
    skip: int = 0,
    limit: int = 100,
    tags: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if tags and tags.strip():
        # Extracción y normalización de los tags del ticket
        ticket_tags = extraer_conjunto_tags(tags)
        
        # Consultar videos de la base de datos para calcular el score por intersección de tags
        todos_videos = db.query(models.VideoTutorial).all()
        scored_videos = []

        for video in todos_videos:
            video_tags = extraer_conjunto_tags(video.tags)
            # 2. Calcular la intersección entre los tags del ticket y los tags de cada video
            interseccion = ticket_tags.intersection(video_tags)
            # 3. Asignar un "score" igual a la cantidad de tags que coincidieron
            score = len(interseccion)

            if score > 0:
                scored_videos.append({
                    "video": video,
                    "score": score,
                    "interseccion": list(interseccion)
                })

        # 4. Ordenar de mayor a menor según el score para que el más relevante quede en el índice 0.
        # Desempate secundario por efectividad (casos_resueltos) y novedad (id).
        scored_videos.sort(
            key=lambda x: (
                x["score"],
                getattr(x["video"], "casos_resueltos", 0) or 0,
                x["video"].id
            ),
            reverse=True
        )

        logger.info(
            f"[Recomendación Videos] Tags del ticket: '{tags}'. Videos coincidentes: {len(scored_videos)}"
        )
        if scored_videos:
            top = scored_videos[0]
            logger.info(
                f"[Recomendación Videos] Top 1 (Score {top['score']}): '{top['video'].titulo}' (ID: {top['video'].id}) "
                f"con tags coincidentes: {top['interseccion']}"
            )

        videos = [item["video"] for item in scored_videos][skip : skip + limit]
    else:
        videos = (
            db.query(models.VideoTutorial)
            .order_by(models.VideoTutorial.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

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
                fecha_subida=video.fecha_subida,
                reproducciones=getattr(video, "reproducciones", 0) or 0,
                casos_resueltos=getattr(video, "casos_resueltos", 0) or 0
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
        fecha_subida=video.fecha_subida,
        reproducciones=getattr(video, "reproducciones", 0) or 0,
        casos_resueltos=getattr(video, "casos_resueltos", 0) or 0
    )


@router.put("/{video_id}", response_model=schemas.VideoRespuesta)
@router.patch("/{video_id}", response_model=schemas.VideoRespuesta)
def update_video(
    video_id: int,
    video_update: schemas.VideoUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza la información de un video tutorial existente en la base de datos (Supabase).
    Campos editables: titulo, descripcion y palabras_clave (tags).
    """
    video = db.query(models.VideoTutorial).filter(models.VideoTutorial.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video tutorial no encontrado")

    if video_update.titulo is not None:
        video.titulo = video_update.titulo.strip()

    if video_update.descripcion is not None:
        video.descripcion = video_update.descripcion.strip()

    tags_val = video_update.palabras_clave if video_update.palabras_clave is not None else video_update.tags
    if tags_val is not None:
        video.tags = tags_val.strip().lower()

    db.commit()
    db.refresh(video)

    client = get_supabase_client()
    storage = client.storage
    url_firmada = generar_url_firmada(storage, video.url_video, 3600)

    return schemas.VideoRespuesta(
        id=video.id,
        titulo=video.titulo,
        descripcion=video.descripcion,
        url_video=url_firmada,
        tags=video.tags,
        fecha_subida=video.fecha_subida,
        reproducciones=getattr(video, "reproducciones", 0) or 0,
        casos_resueltos=getattr(video, "casos_resueltos", 0) or 0
    )


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Elimina un video tutorial y su archivo asociado en Supabase Storage."""
    video = db.query(models.VideoTutorial).filter(models.VideoTutorial.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video tutorial no encontrado")

    # Intentar eliminar de Supabase Storage
    try:
        client = get_supabase_client()
        storage = client.storage
        clean_path = os.path.basename(video.url_video) if "/static/videos/" in video.url_video else video.url_video
        if clean_path and not clean_path.startswith("http"):
            storage.from_(BUCKET_NAME).remove([clean_path])
    except Exception as e:
        logger.warning(f"[Supabase Storage] Error al eliminar archivo de video {video.url_video}: {e}")

    db.delete(video)
    db.commit()
    return {"mensaje": "Video tutorial eliminado exitosamente", "id": video_id}


@router.post("/{video_id}/reproducir")
def registrar_reproduccion(video_id: int, db: Session = Depends(get_db)):
    """Incrementa en 1 el contador de reproducciones del video tutorial."""
    video = db.query(models.VideoTutorial).filter(models.VideoTutorial.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video tutorial no encontrado")

    video.reproducciones = (getattr(video, "reproducciones", 0) or 0) + 1
    db.commit()
    db.refresh(video)
    return {"id": video.id, "reproducciones": video.reproducciones}


@router.post("/{video_id}/resolver")
def registrar_caso_resuelto(video_id: int, db: Session = Depends(get_db)):
    """Incrementa en 1 el contador de casos resueltos por el video tutorial (botón 'Solucioné mi problema')."""
    video = db.query(models.VideoTutorial).filter(models.VideoTutorial.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video tutorial no encontrado")

    video.casos_resueltos = (getattr(video, "casos_resueltos", 0) or 0) + 1
    db.commit()
    db.refresh(video)
    return {"id": video.id, "casos_resueltos": video.casos_resueltos}
