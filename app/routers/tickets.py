from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import shutil
from .. import crud, models, schemas
from ..database import get_db
from ..auth import decode_access_token
from ..utils.ia_analyzer import analizar_ticket_ia

router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
)


@router.post("/", response_model=schemas.TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: Request,
    db: Session = Depends(get_db)
):
    content_type = request.headers.get("content-type", "")
    descripcion = ""
    usuario_id = None
    criticidad = None
    evidencia_url = None

    if "application/json" in content_type:
        body = await request.json()
        descripcion = body.get("descripcion", "")
        criticidad = body.get("criticidad")
        usuario_id = body.get("usuario_id")
        correo = body.get("correo")
        sede = body.get("sede")
        piso = body.get("piso")
        if correo and not usuario_id:
            u = db.query(models.Usuario).filter(models.Usuario.correo == correo.strip()).first()
            if u:
                usuario_id = u.id
    else:
        form = await request.form()
        descripcion = form.get("descripcion", "")
        uid = form.get("usuario_id")
        if uid is not None and str(uid).isdigit():
            usuario_id = int(uid)
        archivo = form.get("archivo")
        if archivo and hasattr(archivo, "filename") and archivo.filename:
            ext = os.path.splitext(archivo.filename)[1] if archivo.filename else ""
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join("static", "evidencias", unique_filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(archivo.file, buffer)
            evidencia_url = f"/static/evidencias/{unique_filename}"

    if not descripcion or len(descripcion.strip()) == 0:
        raise HTTPException(status_code=400, detail="La descripción del ticket es obligatoria.")

    # Si no se pasó usuario_id explícito, extraerlo del token Bearer
    if not usuario_id:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
            payload = decode_access_token(token)
            if payload:
                usuario_id = payload.get("user_id") or payload.get("sub")

    if not usuario_id:
        usuario_id = 1  # Fallback por defecto si no hay usuario asignado
    else:
        try:
            usuario_id = int(usuario_id)
        except (ValueError, TypeError):
            usuario_id = 1

    ia_result = analizar_ticket_ia(descripcion)
    # Si el usuario seleccionó una criticidad específica en el modal, se respeta; sino, se usa IA
    if not criticidad:
        criticidad = ia_result["criticidad"]

    db_ticket = models.Ticket(
        usuario_id=usuario_id,
        descripcion=descripcion,
        evidencia_url=evidencia_url,
        criticidad=criticidad
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    db_ticket.palabras_clave = ia_result["palabras_clave"]
    return db_ticket

@router.get("/", response_model=List[schemas.TicketResponse])
def read_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).order_by(models.Ticket.id.desc()).offset(skip).limit(limit).all()
    for t in tickets:
        t.palabras_clave = analizar_ticket_ia(t.descripcion)["palabras_clave"]
    return tickets

@router.patch("/{ticket_id}/estado", response_model=schemas.TicketResponse)
def update_ticket_state(ticket_id: int, ticket_update: schemas.TicketUpdateEstado, db: Session = Depends(get_db)):
    db_ticket = crud.get_ticket(db, ticket_id=ticket_id)
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    nuevo_estado = ticket_update.estado
    comentario = ticket_update.comentario_tecnico
    
    if nuevo_estado not in ["En Progreso", "Resuelto"]:
        raise HTTPException(status_code=400, detail="Estado inválido. Debe ser 'En Progreso' o 'Resuelto'")
        
    if nuevo_estado == "Resuelto":
        if not comentario or len(comentario.strip()) < 10:
            raise HTTPException(
                status_code=400, 
                detail="Si el estado es 'Resuelto', el comentario_tecnico es obligatorio y debe tener al menos 10 caracteres."
            )
            
    db_ticket.estado = nuevo_estado
    if comentario is not None:
        db_ticket.comentario_tecnico = comentario
        
    db.commit()
    db.refresh(db_ticket)
    db_ticket.palabras_clave = analizar_ticket_ia(db_ticket.descripcion)["palabras_clave"]
    return db_ticket

@router.post("/{ticket_id}/resolver-autoatencion")
def resolver_ticket_autoatencion(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = crud.get_ticket(db, ticket_id=ticket_id)
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    db_ticket.estado = "Resuelto"
    comentario_previo = db_ticket.comentario_tecnico + " | " if db_ticket.comentario_tecnico else ""
    db_ticket.comentario_tecnico = comentario_previo + "El usuario resolvió su problema con el video"
    
    db.commit()
    db.refresh(db_ticket)
    db_ticket.palabras_clave = analizar_ticket_ia(db_ticket.descripcion)["palabras_clave"]
    
    return {
        "mensaje": "Ticket atendido automáticamente por microaprendizaje",
        "ticket": db_ticket
    }

@router.get("/usuario/{usuario_id}", response_model=List[schemas.TicketResponse])
def get_user_tickets(usuario_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).filter(models.Ticket.usuario_id == usuario_id)\
                .order_by(models.Ticket.id.desc()).offset(skip).limit(limit).all()
    for t in tickets:
        t.palabras_clave = analizar_ticket_ia(t.descripcion)["palabras_clave"]
    return tickets
