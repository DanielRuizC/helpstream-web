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
        activo=True,
        telefono=usuario_in.telefono,
        anexo=usuario_in.anexo
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario


@router.get("/roles", response_model=List[schemas.RolResponse])
def listar_roles(db: Session = Depends(get_db)):
    """Lista todos los roles disponibles en el sistema."""
    return db.query(models.Rol).order_by(models.Rol.id).all()


@router.get("/usuarios", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    """Lista todos los usuarios registrados."""
    return db.query(models.Usuario).order_by(models.Usuario.id).all()


@router.get("/usuarios/buscar", response_model=schemas.UsuarioResponse)
def buscar_usuario_por_correo(correo: str, db: Session = Depends(get_db)):
    """Busca un usuario por su correo electrónico."""
    usuario = db.query(models.Usuario).filter(models.Usuario.correo == correo.strip()).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún usuario con el correo: {correo}"
        )
    return usuario


@router.put("/usuarios/{usuario_id}", response_model=schemas.UsuarioResponse)
def actualizar_usuario(usuario_id: int, datos: schemas.UsuarioUpdate, db: Session = Depends(get_db)):
    """Actualiza datos de un usuario existente."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado."
        )

    if datos.nombres is not None:
        usuario.nombres = datos.nombres
    elif getattr(datos, "nombre", None) is not None:
        usuario.nombres = datos.nombre
    if datos.apellidos is not None:
        usuario.apellidos = datos.apellidos
    if datos.correo is not None:
        existente = db.query(models.Usuario).filter(models.Usuario.correo == datos.correo, models.Usuario.id != usuario_id).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo ya pertenece a otro usuario registrado."
            )
        usuario.correo = datos.correo
    if datos.rol_id is not None:
        rol = db.query(models.Rol).filter(models.Rol.id == datos.rol_id).first()
        if not rol:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El rol con ID {datos.rol_id} no existe."
            )
        usuario.rol_id = datos.rol_id
    if datos.activo is not None:
        usuario.activo = datos.activo
    if datos.telefono is not None:
        usuario.telefono = datos.telefono
    if datos.anexo is not None:
        usuario.anexo = datos.anexo

    db.commit()
    db.refresh(usuario)
    return usuario


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
