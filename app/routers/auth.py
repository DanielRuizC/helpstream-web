from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from .. import models, schemas
from ..database import get_db
from ..auth import verify_password, get_password_hash, create_access_token, decode_access_token

router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/local", auto_error=False)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.Usuario:
    """Valida el token Bearer y recupera el usuario autenticado actual."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación no válidas o ausentes.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
            else:
                token = auth_header.strip()

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise credentials_exception

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        pass

    usuario = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not usuario:
        raise credentials_exception

    return usuario


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


@router.patch("/fcm-token")
async def actualizar_fcm_token(
    request: Request,
    datos: Optional[Union[schemas.FCMTokenUpdate, str]] = Body(None),
    current_user: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra o actualiza el identificador del dispositivo móvil (fcm_token)
    para el usuario actualmente autenticado (HU08).
    """
    token_str = None
    if isinstance(datos, schemas.FCMTokenUpdate):
        token_str = datos.fcm_token or datos.token
    elif isinstance(datos, str):
        token_str = datos

    # Respaldo en caso de envío como JSON plano o raw string
    if not token_str:
        try:
            body = await request.json()
            if isinstance(body, dict):
                token_str = body.get("fcm_token") or body.get("token")
            elif isinstance(body, str):
                token_str = body
        except Exception:
            try:
                raw_bytes = await request.body()
                raw_str = raw_bytes.decode("utf-8").strip()
                if raw_str:
                    token_str = raw_str.strip('"')
            except Exception:
                pass

    if not token_str or not token_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere un token FCM válido en el cuerpo de la solicitud."
        )

    current_user.fcm_token = token_str.strip()
    db.commit()
    db.refresh(current_user)

    return {
        "mensaje": "Token FCM guardado correctamente.",
        "usuario_id": current_user.id,
        "fcm_token": current_user.fcm_token
    }

