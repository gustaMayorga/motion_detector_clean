import os
import sys
import asyncio
import logging
import uvicorn
import argparse
from datetime import datetime
from pathlib import Path

# Configuración de logging antes de importar el resto de módulos
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/vigia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger("vigIA")

# Importar componentes del sistema
from src.config.config_loader import load_config
from src.database.db import init_db, get_db
from src.database.models import Camera, User, Role, Permission
from src.events.event_bus import EventBus
from src.processing.video_processor import VideoProcessor
from src.storage.storage_manager import StorageManager
from src.api.websocket import manager as ws_manager, WebSocketEventHandler
from src.api.api import app

class AsyncMock:
    """Un objeto simulado simple para funciones asíncronas"""
    async def __call__(self, *args, **kwargs):
        return None

class VigIASystem:
    """Sistema principal de vigIA que coordina todos los componentes"""
    
    def __init__(self, config_path="configs/config.yaml"):
        """Inicializa el sistema con la configuración especificada"""
        self.logger = logging.getLogger("VigIASystem")
        self.config_path = config_path
        self.config = None
        self.event_bus = None
        self.storage_manager = None
        self.ws_handler = None
        self.video_processors = {}
        self.is_running = False
        
        # Crear directorios necesarios
        os.makedirs("logs", exist_ok=True)
        
    async def initialize(self):
        """Inicializa todos los componentes del sistema"""
        try:
            # Cargar configuración
            self.logger.info("Cargando configuración...")
            self.config = load_config(self.config_path)
            
            # Configurar nivel de logging según configuración
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, self.config["system"]["log_level"]))
            
            # Inicializar base de datos
            self.logger.info("Inicializando base de datos...")
            init_db()
            
            # Verificar datos iniciales
            await self._check_initial_data()
            
            # Inicializar bus de eventos
            self.logger.info("Inicializando bus de eventos...")
            try:
                self.event_bus = EventBus(
                    redis_host=self.config["redis"]["host"],
                    redis_port=self.config["redis"]["port"],
                    redis_db=self.config["redis"]["db"],
                    redis_password=self.config["redis"]["password"],
                )
                
                # Intenta conectar a Redis
                event_bus_connected = await self.event_bus.connect()
                if not event_bus_connected:
                    self.logger.warning("No se pudo conectar al bus de eventos. Continuando en modo limitado...")
                    # Seguir ejecutando aunque Redis no esté disponible
                else:
                    self.logger.info("Bus de eventos inicializado")
            except Exception as e:
                self.logger.warning(f"Error con el bus de eventos: {e}. Continuando en modo limitado...")
                # Crear un bus de eventos simulado para no romper el código que lo usa
                from unittest.mock import MagicMock
                self.event_bus = MagicMock()
                self.event_bus.publish = AsyncMock()
                self.event_bus.subscribe = AsyncMock()
            
            # Iniciar listener de eventos
            await self.event_bus.start_listener()
            
            # Inicializar gestor de almacenamiento
            self.logger.info("Inicializando gestor de almacenamiento...")
            self.storage_manager = StorageManager(self.config_path, self.event_bus)
            await self.storage_manager.initialize()
            self.logger.info("Gestor de almacenamiento inicializado")
            
            # Inicializar procesadores de video
            self.logger.info("Inicializando procesadores de video...")
            with get_db() as db:
                cameras = db.query(Camera).all()
                self.logger.info(f"Encontradas {len(cameras)} cámaras")
                
                for camera in cameras:
                    self.logger.info(f"Inicializando procesador para cámara {camera.id} ({camera.name})")
                    processor = VideoProcessor(camera.id, self.config_path, self.event_bus)
                    if await processor.initialize():
                        self.video_processors[camera.id] = processor
                    else:
                        self.logger.error(f"Error inicializando procesador para cámara {camera.id}")
            
            # Inicializar handler de WebSockets
            self.logger.info("Inicializando manejador de WebSockets...")
            self.ws_handler = WebSocketEventHandler(self.event_bus, ws_manager)
            await self.ws_handler.initialize()
            
            self.logger.info("Sistema vigIA inicializado correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error inicializando el sistema: {e}", exc_info=True)
            return False
    
    async def _check_initial_data(self):
        """Verificar y crear datos iniciales si no existen"""
        try:
            # Crear rol de administrador si no existe
            with get_db() as db:
                admin_role = db.query(Role).filter(Role.name == "admin").first()
                if not admin_role:
                    self.logger.info("Creando rol de administrador...")
                    admin_role = Role(
                        name="admin",
                        description="Administrador del sistema"
                    )
                    db.add(admin_role)
                    db.commit()
                    db.refresh(admin_role)
                    self.logger.info(f"Rol de administrador creado con ID: {admin_role.id}")
                
                # Crear usuario administrador si no existe
                admin = db.query(User).filter(User.username == "admin").first()
                if not admin:
                    self.logger.info("Creando usuario administrador por defecto...")
                    from werkzeug.security import generate_password_hash
                    
                    admin = User(
                        username="admin",
                        email="admin@vigia.local",
                        password_hash=generate_password_hash("admin123"),
                        first_name="Admin",
                        last_name="User",
                        role_id=admin_role.id,
                        is_active=True
                    )
                    db.add(admin)
                    db.commit()
                    self.logger.info(f"Usuario administrador creado: admin / admin123")
                elif admin and not admin.is_active:
                    admin.is_active = True
                    db.commit()
                    self.logger.info("Usuario administrador reactivado")
        except Exception as e:
            self.logger.error(f"Error inicializando datos: {e}")
            raise
    
    async def start(self):
        """Inicia la ejecución de todos los componentes del sistema"""
        if not await self.initialize():
            self.logger.error("Error inicializando el sistema, no se puede iniciar")
            return False
        
        self.is_running = True
        
        # Iniciar procesadores de video
        self.logger.info("Iniciando procesadores de video...")
        for camera_id, processor in self.video_processors.items():
            if not await processor.start():
                self.logger.error(f"Error iniciando procesador para cámara {camera_id}")
        
        # Publicar evento de inicio del sistema
        await self.event_bus.publish("system_started", {
            "version": self.config["system"]["version"],
            "cameras_active": len(self.video_processors),
            "timestamp": datetime.now().isoformat()
        })
        
        self.logger.info("Sistema vigIA en ejecución")
        return True
    
    async def stop(self):
        """Detiene todos los componentes del sistema de manera ordenada"""
        self.logger.info("Deteniendo sistema vigIA...")
        self.is_running = False
        
        # Detener procesadores de video
        for camera_id, processor in self.video_processors.items():
            await processor.stop()
        
        # Detener gestor de almacenamiento
        if self.storage_manager:
            await self.storage_manager.close()
        
        # Detener manejador de WebSockets
        if self.ws_handler:
            await self.ws_handler.close()
        
        # Detener bus de eventos
        if self.event_bus:
            await self.event_bus.close()
        
        self.logger.info("Sistema vigIA detenido")

async def main(config_path, args):
    """Función principal para iniciar el sistema"""
    # Crear e inicializar el sistema
    system = VigIASystem(config_path)
    
    # Iniciar el sistema
    if not await system.start():
        logger.error("Error iniciando el sistema")
        return 1
    
    # Configurar la API
    app.state.system = system
    app.state.event_bus = system.event_bus
    
    # Servir la API con Uvicorn
    config = uvicorn.Config(
        app=app,
        host=system.config["api"]["host"],
        port=system.config["api"]["port"],
        log_level=system.config["system"]["log_level"].lower(),
        reload=args.debug,
        workers=1  # Usar un solo worker debido a la naturaleza asíncrona
    )
    server = uvicorn.Server(config)
    
    # Manejar señales para apagado graceful
    import signal
    
    def signal_handler():
        """Manejador de señales para apagado graceful"""
        logger.info("Recibida señal de terminación")
        asyncio.create_task(system.stop())
    
    # Registrar manejadores de señales
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda sig, frame: signal_handler())
    
    # Iniciar el servidor
    await server.serve()
    
    # Asegurar apagado completo
    await system.stop()
    return 0

if __name__ == "__main__":
    # Crear parser de argumentos
    parser = argparse.ArgumentParser(description="Sistema de Videovigilancia Inteligente vigIA")
    parser.add_argument("--config", type=str, default="configs/config.yaml", help="Ruta al archivo de configuración")
    parser.add_argument("--debug", action="store_true", help="Habilitar modo debug con recarga automática")
    args = parser.parse_args()
    
    # Verificar existencia del archivo de configuración
    if not os.path.exists(args.config):
        logger.error(f"Archivo de configuración no encontrado: {args.config}")
        sys.exit(1)
    
    # Ejecutar la función principal
    try:
        exit_code = asyncio.run(main(args.config, args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Ejecución interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        sys.exit(1) 