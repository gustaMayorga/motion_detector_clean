import os
import json
import logging
import shutil
import time
import sqlite3
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import asyncio

from typing import Optional, Dict, List, Any, Tuple
from src.config.config_loader import load_config
from src.events.event_bus import EventBus, EventTypes
from src.database.models import Camera, Recording, Alert
from src.database.db import get_db

class StorageManager:
    """
    Gestor de almacenamiento para grabaciones y snapshots
    Maneja la creación de directorios, limpieza y rotación de archivos
    """
    
    def __init__(self, config_path: str = "configs/config.yaml", event_bus: Optional[EventBus] = None):
        """Inicializa el gestor de almacenamiento"""
        self.logger = logging.getLogger("StorageManager")
        
        # Cargar configuración
        self.config = load_config(config_path)
        self.storage_config = self.config["storage"]
        
        # Directorios base
        self.recordings_dir = self.storage_config["recordings_dir"]
        self.snapshots_dir = self.storage_config["snapshots_dir"]
        
        # Estadísticas de uso
        self.disk_usage = 0
        self.disk_free = 0
        self.disk_total = 0
        
        # Crear directorios si no existen
        os.makedirs(self.recordings_dir, exist_ok=True)
        os.makedirs(self.snapshots_dir, exist_ok=True)
        
        # Bus de eventos
        self.event_bus = event_bus
        
        # Estado
        self.is_cleaning = False
        self.pending_recordings = {}  # camera_id: {recording_info}
    
    async def initialize(self):
        """Inicializa el gestor de almacenamiento"""
        try:
            # Conexión al evento bus si no está ya conectado
            if self.event_bus is None:
                self.event_bus = EventBus(
                    redis_host=self.config["redis"]["host"],
                    redis_port=self.config["redis"]["port"],
                    redis_db=self.config["redis"]["db"],
                    redis_password=self.config["redis"]["password"],
                )
                await self.event_bus.connect()
            
            # Verificar estado de almacenamiento
            self.update_disk_stats()
            
            # Realizar limpieza inicial si está habilitado
            if self.storage_config["auto_clean"] and self.disk_usage > self.storage_config["max_disk_usage_percent"]:
                await self.clean_old_recordings()
            
            # Suscribirse a eventos relevantes
            await self.event_bus.subscribe(EventTypes.RECORDING_STARTED, self.handle_recording_started)
            await self.event_bus.subscribe(EventTypes.RECORDING_STOPPED, self.handle_recording_stopped)
            await self.event_bus.subscribe(EventTypes.ALERT_GENERATED, self.handle_alert_generated)
            
            # Iniciar listener de eventos
            await self.event_bus.start_listener()
            
            self.logger.info("Gestor de almacenamiento inicializado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error inicializando gestor de almacenamiento: {e}")
            return False
    
    def update_disk_stats(self):
        """Actualiza estadísticas de uso de disco"""
        try:
            # Obtener estadísticas de la unidad donde está el directorio de grabaciones
            stat = shutil.disk_usage(self.recordings_dir)
            
            self.disk_total = stat.total
            self.disk_free = stat.free
            self.disk_usage = 100 - (stat.free / stat.total * 100)
            
            self.logger.debug(f"Estadísticas de disco: Uso {self.disk_usage:.1f}%, Libre {self.disk_free / (1024**3):.1f} GB")
            return True
            
        except Exception as e:
            self.logger.error(f"Error actualizando estadísticas de disco: {e}")
            return False
    
    def get_snapshot_path(self, camera_id: int, timestamp: Optional[datetime] = None) -> str:
        """Construye la ruta para un snapshot"""
        if timestamp is None:
            timestamp = datetime.now()
        
        year_month = timestamp.strftime("%Y_%m")
        day = timestamp.strftime("%d")
        filename = f"cam_{camera_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        
        # Crear estructura de directorios
        path = os.path.join(self.snapshots_dir, f"camera_{camera_id}", year_month, day)
        os.makedirs(path, exist_ok=True)
        
        return os.path.join(path, filename)
    
    async def save_snapshot(self, camera_id: int, frame, timestamp: Optional[datetime] = None) -> Optional[str]:
        """Guarda un snapshot en disco"""
        try:
            if timestamp is None:
                timestamp = datetime.now()
                
            # Construir ruta
            snapshot_path = self.get_snapshot_path(camera_id, timestamp)
            
            # Guardar imagen
            cv2.imwrite(snapshot_path, frame)
            
            self.logger.debug(f"Snapshot guardado: {snapshot_path}")
            
            # Publicar evento
            if self.event_bus:
                await self.event_bus.publish(EventTypes.SNAPSHOT_SAVED, {
                    "camera_id": camera_id,
                    "path": snapshot_path,
                    "timestamp": timestamp.isoformat(),
                })
            
            return snapshot_path
            
        except Exception as e:
            self.logger.error(f"Error guardando snapshot: {e}")
            return None
    
    async def close(self):
        """Cierra el gestor de almacenamiento"""
        try:
            # Detener listener de eventos
            if self.event_bus:
                await self.event_bus.stop_listener()
            
            # Cerrar writers pendientes
            for camera_id, rec_info in self.pending_recordings.items():
                if "writer" in rec_info and rec_info["writer"]:
                    rec_info["writer"].release()
            
            self.pending_recordings = {}
            
            self.logger.info("Gestor de almacenamiento cerrado")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cerrando gestor de almacenamiento: {e}")
            return False

    async def handle_recording_started(self, channel: str, data: dict):
        """Manejador para evento de inicio de grabación"""
        self.logger.info(f"Grabación iniciada: {data}")
        try:
            camera_id = data.get('camera_id')
            if not camera_id:
                self.logger.error("Evento de grabación sin camera_id")
                return
            
            # Agregar a grabaciones pendientes
            self.pending_recordings[camera_id] = {
                'start_time': datetime.now(),
                'metadata': data
            }
        except Exception as e:
            self.logger.error(f"Error manejando evento de inicio de grabación: {e}")
        
    async def handle_recording_stopped(self, channel: str, data: dict):
        """Manejador para evento de fin de grabación"""
        self.logger.info(f"Grabación detenida: {data}")
        try:
            camera_id = data.get('camera_id')
            if not camera_id or camera_id not in self.pending_recordings:
                self.logger.error(f"Evento de fin de grabación para cámara no iniciada: {camera_id}")
                return
            
            # Procesar fin de grabación
            del self.pending_recordings[camera_id]
        except Exception as e:
            self.logger.error(f"Error manejando evento de fin de grabación: {e}")

    async def handle_alert_generated(self, channel: str, data: dict):
        """Manejador para evento de alerta generada"""
        self.logger.info(f"Alerta generada: {data}")
        try:
            # Obtener metadatos relevantes
            camera_id = data.get('camera_id')
            alert_id = data.get('alert_id')
            
            if not camera_id:
                self.logger.error("Evento de alerta sin camera_id")
                return
            
            # Guardar snapshot si hay frame disponible
            if 'frame' in data:
                snapshot_path = await self.save_snapshot(
                    camera_id, 
                    data['frame'],
                    datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat()))
                )
                
                # Asociar snapshot a la alerta en la base de datos
                if snapshot_path and alert_id:
                    with get_db() as db:
                        alert = db.query(Alert).filter(Alert.id == alert_id).first()
                        if alert:
                            alert.snapshot_path = snapshot_path
                            db.commit()
                            
        except Exception as e:
            self.logger.error(f"Error manejando evento de alerta: {e}")


class LocalStorage:
    """Backend de almacenamiento local en disco"""
    def __init__(self, config):
        self.config = config
        self.base_path = config.get('base_path', 'data/videos')
        self.structure = config.get('structure', '{year}/{month}/{day}/{camera_id}')
        self.logger = logging.getLogger('LocalStorage')
        
        # Crear directorio base si no existe
        os.makedirs(self.base_path, exist_ok=True)
        
    def _get_storage_path(self, metadata):
        """Generar estructura de directorios basada en metadatos"""
        timestamp = metadata.get('timestamp', time.time())
        dt = datetime.fromtimestamp(timestamp)
        
        # Variables para reemplazar en la estructura
        vars = {
            'year': dt.strftime('%Y'),
            'month': dt.strftime('%m'),
            'day': dt.strftime('%d'),
            'hour': dt.strftime('%H'),
            'camera_id': metadata.get('camera_id', 'unknown'),
            'event_type': metadata.get('event_type', 'recording')
        }
        
        # Reemplazar variables en la estructura
        dir_structure = self.structure.format(**vars)
        full_path = os.path.join(self.base_path, dir_structure)
        
        # Crear directorio si no existe
        os.makedirs(full_path, exist_ok=True)
        
        return full_path
        
    def store(self, source_path, metadata):
        """Almacenar un archivo en el sistema de archivos local"""
        try:
            if not os.path.exists(source_path):
                self.logger.error(f"Source file not found: {source_path}")
                return None
                
            # Generar estructura de directorios
            dest_dir = self._get_storage_path(metadata)
            
            # Generar nombre de archivo basado en timestamp y metadatos
            timestamp = metadata.get('timestamp', time.time())
            dt = datetime.fromtimestamp(timestamp)
            
            # Obtener extensión del archivo original
            _, ext = os.path.splitext(source_path)
            if not ext:
                ext = '.mp4'  # Default para videos
                
            # Nombre final: camera_eventtype_timestamp.ext
            filename = f"{metadata.get('camera_id', 'cam')}_{metadata.get('event_type', 'rec')}_{dt.strftime('%Y%m%d_%H%M%S')}{ext}"
            
            # Ruta completa de destino
            dest_path = os.path.join(dest_dir, filename)
            
            # Si el archivo origen es diferente al destino, copiar
            if os.path.abspath(source_path) != os.path.abspath(dest_path):
                shutil.copy2(source_path, dest_path)
                self.logger.info(f"File copied: {source_path} -> {dest_path}")
                
            return dest_path
            
        except Exception as e:
            self.logger.error(f"Error storing file: {e}")
            return None
            
    def retrieve(self, path):
        """Verificar si un archivo existe y es accesible"""
        if os.path.exists(path) and os.access(path, os.R_OK):
            return path
        return None
        
    def delete(self, path):
        """Eliminar un archivo"""
        try:
            if os.path.exists(path):
                os.remove(path)
                self.logger.info(f"File deleted: {path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting file: {e}")
            return False
            
    def is_managed_path(self, path):
        """Verificar si una ruta está dentro del sistema gestionado"""
        try:
            base = os.path.abspath(self.base_path)
            path = os.path.abspath(path)
            return path.startswith(base)
        except:
            return False


class S3Storage:
    """Backend de almacenamiento en Amazon S3"""
    def __init__(self, config):
        self.config = config
        self.bucket = config.get('bucket')
        self.prefix = config.get('prefix', '')
        self.credentials_profile = config.get('credentials_profile', 'default')
        self.region = config.get('region', 'us-east-1')
        self.logger = logging.getLogger('S3Storage')
        self._s3_client = None
        
    @property
    def s3_client(self):
        """Obtener cliente S3 con inicialización perezosa"""
        if self._s3_client is None:
            try:
                import boto3
                session = boto3.Session(profile_name=self.credentials_profile)
                self._s3_client = session.client('s3', region_name=self.region)
            except ImportError:
                self.logger.error("boto3 package not installed. Install with: pip install boto3")
                raise
                
        return self._s3_client
        
    def _get_s3_key(self, source_path, metadata):
        """Generar clave S3 para el archivo"""
        timestamp = metadata.get('timestamp', time.time())
        dt = datetime.fromtimestamp(timestamp)
        
        # Generar estructura de directorios en S3
        year = dt.strftime('%Y')
        month = dt.strftime('%m')
        day = dt.strftime('%d')
        camera_id = metadata.get('camera_id', 'unknown')
        
        # Nombre del archivo
        filename = os.path.basename(source_path)
        
        # Combinar para formar la clave S3
        s3_key = f"{self.prefix}{year}/{month}/{day}/{camera_id}/{filename}"
        
        return s3_key.lstrip('/')
        
    def store(self, source_path, metadata):
        """Almacenar un archivo en S3"""
        try:
            if not os.path.exists(source_path):
                self.logger.error(f"Source file not found: {source_path}")
                return None
                
            # Generar clave S3
            s3_key = self._get_s3_key(source_path, metadata)
            
            # Preparar metadatos para S3
            s3_metadata = {
                'camera-id': str(metadata.get('camera_id', 'unknown')),
                'event-type': str(metadata.get('event_type', 'recording')),
                'timestamp': str(int(metadata.get('timestamp', time.time())))
            }
            
            # Subir archivo a S3
            self.s3_client.upload_file(
                source_path, 
                self.bucket, 
                s3_key,
                ExtraArgs={
                    'Metadata': s3_metadata,
                    'ContentType': 'video/mp4'
                }
            )
            
            # Generar URL
            s3_url = f"s3://{self.bucket}/{s3_key}"
            
            self.logger.info(f"File uploaded to S3: {source_path} -> {s3_url}")
            return s3_url
            
        except Exception as e:
            self.logger.error(f"Error uploading to S3: {e}")
            return None
            
    def retrieve(self, s3_url):
        """Descargar un archivo de S3 a una ubicación temporal"""
        try:
            # Parsear URL de S3
            if not s3_url.startswith('s3://'):
                self.logger.error(f"Invalid S3 URL: {s3_url}")
                return None
                
            parts = s3_url[5:].split('/', 1)
            if len(parts) != 2:
                self.logger.error(f"Invalid S3 URL format: {s3_url}")
                return None
                
            bucket = parts[0]
            s3_key = parts[1]
            
            # Crear directorio temporal para la descarga
            temp_dir = os.path.join(tempfile.gettempdir(), 'security_videos')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Nombre de archivo local
            local_filename = os.path.basename(s3_key)
            local_path = os.path.join(temp_dir, local_filename)
            
            # Descargar archivo
            self.s3_client.download_file(bucket, s3_key, local_path)
            
            self.logger.info(f"File downloaded from S3: {s3_url} -> {local_path}")
            return local_path
            
        except Exception as e:
            self.logger.error(f"Error downloading from S3: {e}")
            return None
            
    def delete(self, s3_url):
        """Eliminar un archivo de S3"""
        try:
            # Parsear URL de S3
            if not s3_url.startswith('s3://'):
                self.logger.error(f"Invalid S3 URL: {s3_url}")
                return False
                
            parts = s3_url[5:].split('/', 1)
            if len(parts) != 2:
                self.logger.error(f"Invalid S3 URL format: {s3_url}")
                return False
                
            bucket = parts[0]
            s3_key = parts[1]
            
            # Eliminar archivo
            self.s3_client.delete_object(Bucket=bucket, Key=s3_key)
            
            self.logger.info(f"File deleted from S3: {s3_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting from S3: {e}")
            return False
            
    def is_managed_path(self, path):
        """Verificar si una ruta está dentro del sistema gestionado"""
        return path.startswith(f"s3://{self.bucket}/{self.prefix}") 