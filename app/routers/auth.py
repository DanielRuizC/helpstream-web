from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import verify_password, create_access_token

router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"]
)


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
