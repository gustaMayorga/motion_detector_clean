import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Query, Path, Header, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr

from src.config.config_loader import load_config
from src.database.db import get_db
from src.database.models import User, Camera, Zone, Alert, Recording
from src.events.event_bus import EventBus, EventTypes
from src.camera_vendors.hikvision import HikvisionVendor
from src.camera_vendors.dahua import DahuaVendor

# Cargar configuración
config = load_config("configs/config.yaml")

# Configurar logger
logging.basicConfig(
    level=getattr(logging, config["system"]["log_level"]),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("API")

# Inicializar FastAPI
app = FastAPI(
    title="vigIA API",
    description="API para sistema de videovigilancia inteligente",
    version=config["system"]["version"],
)

# Siempre habilitar CORS si hay orígenes definidos
if "cors_origins" in config["api"] and config["api"]["cors_origins"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["api"]["cors_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Configurar autenticación
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
JWT_SECRET = os.environ.get("JWT_SECRET", config["api"]["jwt_secret"])
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = config["api"]["jwt_expiration"]

# Inicializar bus de eventos
event_bus = EventBus(
    redis_host=config["redis"]["host"],
    redis_port=config["redis"]["port"],
    redis_db=config["redis"]["db"],
    redis_password=config["redis"]["password"],
)

# Inicializar vendors de cámaras
camera_vendors = {
    "hikvision": HikvisionVendor(),
    "dahua": DahuaVendor(),
}

# Modelos de datos para la API
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user_id: int
    username: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: int = 2  # Por defecto rol básico

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime

class CameraCreate(BaseModel):
    camera_id: str
    name: str
    location: Optional[str] = None
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    vendor: str
    model: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    fps: Optional[int] = None
    is_enabled: bool = True
    config: Optional[Dict[str, Any]] = None

class CameraResponse(BaseModel):
    id: int
    camera_id: str
    name: str
    location: Optional[str] = None
    vendor: str
    model: Optional[str] = None
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    fps: Optional[int] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

class ZoneCreate(BaseModel):
    camera_id: int
    name: str
    type: str
    points: List[List[int]]
    color: Optional[str] = None
    is_active: bool = True

class ZoneResponse(BaseModel):
    id: int
    camera_id: int
    name: str
    type: str
    points: List[List[int]]
    color: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class AlertResponse(BaseModel):
    id: int
    camera_id: int
    event_type: str
    priority: str
    timestamp: datetime
    screenshot_path: Optional[str] = None
    is_acknowledged: bool
    created_at: datetime

# Funciones auxiliares
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtiene el usuario actual a partir del token JWT"""
    try:
        # Log detallado para depuración
        logger.debug(f"Token recibido: {token[:15]}...")
        
        # Decodificar token con manejo de errores específicos
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token inválido: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extraer y convertir el ID de usuario
        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("Token sin ID de usuario (sub)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: falta ID de usuario",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Convertir ID si es necesario
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
        
        logger.debug(f"ID obtenido del token: {user_id}")
        
        # Obtener usuario de la base de datos
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado: ID {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario no encontrado",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if not user.is_active:
                logger.warning(f"Usuario inactivo: {user.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario inactivo",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
        logger.debug(f"Usuario autenticado: {user.username} (ID: {user_id})")
        return user
            
    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        logger.error(f"Error inesperado validando token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(user_id: int, username: str) -> str:
    """Crea un token JWT para el usuario"""
    try:
        expires_delta = timedelta(seconds=JWT_EXPIRATION_SECONDS)
        expire = datetime.utcnow() + expires_delta
        
        # Necesitamos que sub sea un string según el estándar JWT
        user_id_str = str(user_id)
        
        to_encode = {
            "sub": user_id_str,  # Siempre como string
            "username": username,
            "exp": expire,
        }
        
        logger.debug(f"Creando token para usuario: {username} (ID: {user_id})")
        logger.debug(f"Payload para codificar: {to_encode}")
        
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Manejar diferencias entre versiones de PyJWT
        if isinstance(encoded_jwt, bytes):
            encoded_jwt = encoded_jwt.decode('utf-8')
            
        logger.debug(f"Token generado: {encoded_jwt[:20]}...")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creando token: {e}", exc_info=True)
        raise

# Evento de inicio y cierre
@app.on_event("startup")
async def startup_event():
    # Conectar al bus de eventos
    await event_bus.connect()
    logger.info("API iniciada correctamente")

@app.on_event("shutdown")
async def shutdown_event():
    # Cerrar conexiones
    await event_bus.close()
    logger.info("API cerrada correctamente")

# Endpoints de autenticación
@app.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
):
    """Endpoint para obtener un token de acceso"""
    try:
        logger.info(f"Intento de inicio de sesión: {form_data.username}")
        
        with get_db() as db:
            user = db.query(User).filter(User.username == form_data.username).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado: {form_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario o contraseña incorrectos",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if not user.is_active:
                logger.warning(f"Intento de acceso con usuario inactivo: {form_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario inactivo",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Verificar contraseña
            from werkzeug.security import check_password_hash
            password_valid = check_password_hash(user.password_hash, form_data.password)
            
            if not password_valid:
                logger.warning(f"Contraseña incorrecta para usuario: {form_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario o contraseña incorrectos",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Actualizar último login
            user.last_login = datetime.utcnow()
            db.commit()
            
            # Crear token
            access_token = create_access_token(user.id, user.username)
            
            logger.info(f"Inicio de sesión exitoso: {form_data.username}")
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": JWT_EXPIRATION_SECONDS,
                "user_id": user.id,
                "username": user.username,
            }
    
    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        logger.error(f"Error durante la autenticación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        )

# Endpoints de usuarios
@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, current_user: User = Depends(get_current_user)):
    # Verificar permisos (simplificado)
    if current_user.role_id != 1:  # Asumir que rol 1 es admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para crear usuarios",
        )
    
    with get_db() as db:
        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(
            (User.username == user.username) | (User.email == user.email)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario o email ya existe",
            )
        
        # Crear nuevo usuario
        # En un sistema real se haría hash de la contraseña
        new_user = User(
            username=user.username,
            email=user.email,
            password_hash=user.password,  # En realidad se guardaría el hash
            first_name=user.first_name,
            last_name=user.last_name,
            role_id=user.role_id,
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return new_user

# Endpoints de cámaras
@app.get("/api/cameras", response_model=List[CameraResponse])
async def get_cameras(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    with get_db() as db:
        query = db.query(Camera)
        
        # Aplicar filtros
        if name:
            query = query.filter(Camera.name.ilike(f"%{name}%"))
        if enabled is not None:
            query = query.filter(Camera.is_enabled == enabled)
        
        # Ejecutar consulta con paginación
        cameras = query.offset(skip).limit(limit).all()
        return cameras

@app.post("/api/cameras", response_model=CameraResponse)
async def create_camera(camera: CameraCreate, current_user: User = Depends(get_current_user)):
    # Verificar permisos
    if current_user.role_id != 1:  # Admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para crear cámaras",
        )
    
    with get_db() as db:
        # Verificar si ya existe cámara con mismo ID
        existing_camera = db.query(Camera).filter(Camera.camera_id == camera.camera_id).first()
        if existing_camera:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una cámara con ID {camera.camera_id}",
            )
        
        # Crear nueva cámara
        new_camera = Camera(
            camera_id=camera.camera_id,
            name=camera.name,
            location=camera.location,
            url=camera.url,
            username=camera.username,
            password=camera.password,
            vendor=camera.vendor,
            model=camera.model,
            resolution_width=camera.resolution_width,
            resolution_height=camera.resolution_height,
            fps=camera.fps,
            is_enabled=camera.is_enabled,
            config=camera.config or {},
        )
        
        db.add(new_camera)
        db.commit()
        db.refresh(new_camera)
        
        # Notificar a través del bus de eventos
        await event_bus.publish("camera_created", {
            "camera_id": new_camera.id,
            "camera_name": new_camera.name,
            "created_by": current_user.id,
        })
        
        return new_camera

@app.get("/api/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: int, current_user: User = Depends(get_current_user)):
    with get_db() as db:
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cámara con ID {camera_id} no encontrada",
            )
        return camera

# Endpoints de zonas
@app.get("/api/cameras/{camera_id}/zones", response_model=List[ZoneResponse])
async def get_zones(
    camera_id: int,
    current_user: User = Depends(get_current_user),
):
    with get_db() as db:
        # Verificar que la cámara existe
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cámara con ID {camera_id} no encontrada",
            )
        
        # Obtener zonas de la cámara
        zones = db.query(Zone).filter(Zone.camera_id == camera_id).all()
        return zones

@app.post("/api/cameras/{camera_id}/zones", response_model=ZoneResponse)
async def create_zone(
    camera_id: int,
    zone: ZoneCreate,
    current_user: User = Depends(get_current_user),
):
    # Verificar que camera_id en la ruta coincide con el de la zona
    if zone.camera_id != camera_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="camera_id en la ruta no coincide con el de la zona",
        )
    
    with get_db() as db:
        # Verificar que la cámara existe
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cámara con ID {camera_id} no encontrada",
            )
        
        # Crear nueva zona
        new_zone = Zone(
            camera_id=zone.camera_id,
            name=zone.name,
            type=zone.type,
            points=zone.points,
            color=zone.color,
            is_active=zone.is_active,
        )
        
        db.add(new_zone)
        db.commit()
        db.refresh(new_zone)
        
        # Notificar a través del bus de eventos
        await event_bus.publish("zone_created", {
            "zone_id": new_zone.id,
            "zone_name": new_zone.name,
            "camera_id": camera_id,
            "created_by": current_user.id,
        })
        
        return new_zone

# Endpoints de alertas
@app.get("/api/alerts", response_model=List[AlertResponse])
async def get_alerts(
    skip: int = 0,
    limit: int = 100,
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    acknowledged: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    with get_db() as db:
        query = db.query(Alert)
        
        # Aplicar filtros
        if camera_id:
            query = query.filter(Alert.camera_id == camera_id)
        if event_type:
            query = query.filter(Alert.event_type == event_type)
        if start_date:
            query = query.filter(Alert.timestamp >= start_date)
        if end_date:
            query = query.filter(Alert.timestamp <= end_date)
        if acknowledged is not None:
            query = query.filter(Alert.is_acknowledged == acknowledged)
        
        # Ordenar por timestamp descendente
        query = query.order_by(Alert.timestamp.desc())
        
        # Ejecutar consulta con paginación
        alerts = query.offset(skip).limit(limit).all()
        return alerts

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    with get_db() as db:
        # Buscar alerta
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alerta con ID {alert_id} no encontrada",
            )
        
        # Actualizar alerta
        alert.is_acknowledged = True
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()
        if notes:
            alert.notes = notes
        
        db.commit()
        
        # Notificar a través del bus de eventos
        await event_bus.publish("alert_acknowledged", {
            "alert_id": alert.id,
            "acknowledged_by": current_user.id,
            "camera_id": alert.camera_id,
        })
        
        return {"message": "Alerta confirmada correctamente"}

# Endpoint de estado del sistema
@app.get("/api/system/status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    # En un sistema real, se obtendrían datos reales
    return {
        "status": "online",
        "version": config["system"]["version"],
        "uptime": "10h 23m",
        "cpu_usage": 35.2,
        "memory_usage": 42.7,
        "disk_usage": 68.4,
        "cameras_online": 5,
        "cameras_offline": 1,
        "alerts_today": 12,
        "alerts_pending": 3,
    }

# Añadir este endpoint al inicio de los endpoints
@app.get("/")
async def root():
    """Redirecciona a la documentación de la API"""
    return {
        "name": "vigIA API",
        "version": config["system"]["version"],
        "documentation": "/docs",
        "status": "online",
        "endpoints": [
            {"path": "/api/system/status", "method": "GET", "description": "Estado del sistema"},
            {"path": "/api/cameras", "method": "GET", "description": "Listar cámaras"},
            {"path": "/api/alerts", "method": "GET", "description": "Listar alertas"},
            {"path": "/token", "method": "POST", "description": "Obtener token de autenticación"}
        ]
    }

@app.post("/verify-token")
async def verify_token(authorization: str = Header(...)):
    try:
        # Extraer el token del header
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            return {"status": "error", "message": "Se requiere autenticación Bearer"}
        
        # Información sobre el token
        token_info = {
            "token_length": len(token),
            "token_prefix": token[:20] + "...",
        }
        
        # Intentar decodificar el token
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            decoded = {
                "status": "success",
                "payload": payload,
                "user_id": payload.get("sub"),
                "username": payload.get("username"),
                "expiration": datetime.fromtimestamp(payload.get("exp")).isoformat() if "exp" in payload else None,
            }
            
            # Verificar usuario en la base de datos
            user_id = payload.get("sub")
            with get_db() as db:
                if isinstance(user_id, str) and user_id.isdigit():
                    user_id = int(user_id)
                
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    decoded["user_found"] = True
                    decoded["user_details"] = {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "is_active": user.is_active,
                    }
                else:
                    decoded["user_found"] = False
            
            return {**token_info, **decoded}
        except Exception as e:
            return {
                **token_info,
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }
    except Exception as e:
        return {"status": "error", "message": f"Error al procesar: {str(e)}"}

# Devolver la API
app = app 

if __name__ == "__main__":
    import uvicorn
    # Cambiar el puerto aquí
    uvicorn.run(app, host="0.0.0.0", port=8800) 