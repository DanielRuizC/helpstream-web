from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db
from ..auth import verify_password, get_password_hash, create_access_token

router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"]
)


@router.post("/registro", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario_in: schemas.UsuarioRegistro, db: Session = Depends(get_db)):
    """
    Registro de nuevos usuarios definiendo su rol (Usuario final, Analista de TI, Jefe).
    Valida unicidad de correo, valida rol_id, encripta contraseña con bcrypt e inserta en Supabase.
    """
    # 1. Validar que no exista un usuario registrado con el mismo correo
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.correo == usuario_in.correo).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    # 2. Validar que el rol_id exista en la tabla roles
    rol = db.query(models.Rol).filter(models.Rol.id == usuario_in.rol_id).first()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El rol con ID {usuario_in.rol_id} no existe en el sistema."
        )

    # 3. Encriptar contraseña utilizando la función hash del proyecto
    password_encriptada = get_password_hash(usuario_in.password)

    # 4. Crear nuevo usuario en Supabase (PostgreSQL)
    nuevo_usuario = models.Usuario(
        nombres=usuario_in.nombre,
        apellidos="",
        correo=usuario_in.correo,
        password_hash=password_encriptada,
        rol_id=usuario_in.rol_id,
        activo=True
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario


@router.get("/roles", response_model=List[schemas.RolResponse])
def listar_roles(db: Session = Depends(get_db)):
    """Lista todos los roles disponibles en el sistema."""
    return db.query(models.Rol).order_by(models.Rol.id).all()


@router.post("/login/local", response_model=schemas.Token)
def login_local(credenciales: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):

    """
    Autenticación local mediante correo y contraseña.
    Valida las credenciales contra la base de datos y retorna un token de acceso JWT con user_id y rol_id.
    """
    # 1. Buscar usuario por correo electrónico (recibido en el campo username del formulario)
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == credenciales.username).first()

    # 2. Validar existencia y verificación de contraseña
    if not usuario or not verify_password(credenciales.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Validar si el usuario se encuentra activo
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario se encuentra inactivo en el sistema"
        )

    # 4. Inyectar user_id y rol_id en el payload del token JWT
    payload = {
        "sub": str(usuario.id),
        "user_id": usuario.id,
        "rol_id": usuario.rol_id,
        "correo": usuario.correo
    }
    access_token = create_access_token(data=payload)

    # 5. Retornar formato JSON con el token generado
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
