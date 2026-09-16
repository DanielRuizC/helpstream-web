from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import shutil
from .. import crud, models, schemas
from ..database import get_db
from ..utils.ia_analyzer import analizar_ticket_ia

router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
)


@router.post("/", response_model=schemas.TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    descripcion: str = Form(...),
    usuario_id: int = Form(...),
    archivo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    evidencia_url = None
    if archivo:
        ext = os.path.splitext(archivo.filename)[1] if archivo.filename else ""
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join("static", "evidencias", unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)
        evidencia_url = f"/static/evidencias/{unique_filename}"
        
    ia_result = analizar_ticket_ia(descripcion)
    
    db_ticket = models.Ticket(
        usuario_id=usuario_id,
        descripcion=descripcion,
        evidencia_url=evidencia_url,
        criticidad=ia_result["criticidad"]
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
