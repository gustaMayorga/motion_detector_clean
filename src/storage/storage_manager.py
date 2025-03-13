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

class StorageManager:
    def __init__(self, config_path="configs/storage.json"):
        self.config = self._load_config(config_path)
        self.storage_backends = self._init_backends()
        self.logger = logging.getLogger('StorageManager')
        self.video_indexer = None  # Se puede inicializar externamente
        self.lock = threading.RLock()
        self._cleanup_thread = None
        self._stop_event = threading.Event()
        
        # Iniciar limpieza automática si está habilitada
        if self.config.get('auto_cleanup', False):
            self._start_cleanup_thread()
        
    def _load_config(self, config_path):
        """Cargar configuración desde archivo JSON"""
        if not os.path.exists(config_path):
            return {
                "default_backend": "local",
                "auto_cleanup": True,
                "cleanup_interval": 3600,  # segundos (1 hora)
                "retention_policy": {
                    "default": 30,  # días
                    "theft_detected": 90,  # días
                    "perimeter_breach": 60,  # días
                    "tailgating": 60  # días
                },
                "local": {
                    "base_path": "data/videos",
                    "structure": "{year}/{month}/{day}/{camera_id}"
                },
                "s3": {
                    "bucket": "security-videos",
                    "prefix": "videos/",
                    "credentials_profile": "default"
                }
            }
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading storage config: {e}")
            return {}
            
    def _init_backends(self):
        """Inicializar backends de almacenamiento configurados"""
        backends = {}
        
        if 'local' in self.config:
            backends['local'] = LocalStorage(self.config['local'])
            
        if 's3' in self.config:
            try:
                backends['s3'] = S3Storage(self.config['s3'])
            except ImportError:
                self.logger.warning("S3 backend configured but boto3 not installed")
            
        # Aquí se pueden agregar más backends...
        
        return backends
        
    def _get_backend(self, backend_name=None):
        """Obtener instancia de backend por nombre o el predeterminado"""
        if backend_name and backend_name in self.storage_backends:
            return self.storage_backends[backend_name]
            
        default_backend = self.config.get('default_backend', 'local')
        if default_backend in self.storage_backends:
            return self.storage_backends[default_backend]
            
        # Si no hay backend disponible, usar el primero que encontremos
        if self.storage_backends:
            return next(iter(self.storage_backends.values()))
            
        raise ValueError("No storage backends available")
        
    def _start_cleanup_thread(self):
        """Iniciar hilo de limpieza automática"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._stop_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True
            )
            self._cleanup_thread.start()
            self.logger.info("Cleanup thread started")
            
    def _cleanup_loop(self):
        """Bucle de limpieza automática"""
        interval = self.config.get('cleanup_interval', 3600)
        
        while not self._stop_event.is_set():
            try:
                self.cleanup_old_videos()
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                
            # Esperar hasta el próximo ciclo o hasta que se solicite detener
            self._stop_event.wait(interval)
            
    def store_video(self, video_data, metadata, backend=None):
        """Almacenar video en backend especificado o predeterminado"""
        try:
            # Determinar el backend a usar
            storage_backend = self._get_backend(backend)
            
            # Si video_data es un path, asumimos que es un archivo ya existente
            if isinstance(video_data, str) and os.path.exists(video_data):
                source_path = video_data
            else:
                # TODO: Implementar lógica para guardar datos de video en memoria (numpy array o bytes)
                self.logger.error("Storing video from memory data not implemented")
                return None
                
            # Almacenar en el backend
            stored_path = storage_backend.store(source_path, metadata)
            
            # Indexar video si tenemos video_indexer configurado
            if self.video_indexer and stored_path:
                video_id = self.video_indexer._index_video(stored_path, metadata)
                
                # Indexar evento si hay información relevante
                if video_id and 'event_id' in metadata and 'event_type' in metadata:
                    self.video_indexer.index_event(
                        {
                            'id': metadata['event_id'],
                            'type': metadata['event_type']
                        },
                        stored_path,
                        metadata.get('start_time', 0),
                        metadata.get('end_time', time.time())
                    )
                    
                return {
                    'path': stored_path,
                    'video_id': video_id,
                    'backend': storage_backend.__class__.__name__
                }
                
            return {'path': stored_path, 'backend': storage_backend.__class__.__name__}
            
        except Exception as e:
            self.logger.error(f"Error storing video: {e}")
            return None
            
    def register_video(self, video_path, metadata):
        """Registrar un video ya existente en el sistema"""
        try:
            if not os.path.exists(video_path):
                self.logger.error(f"Video file not found: {video_path}")
                return None
                
            # Indexar video si tenemos video_indexer configurado
            if self.video_indexer:
                video_id = self.video_indexer._index_video(video_path, metadata)
                
                # Indexar evento si hay información relevante
                if video_id and 'event_id' in metadata and 'event_type' in metadata:
                    self.video_indexer.index_event(
                        {
                            'id': metadata['event_id'],
                            'type': metadata['event_type']
                        },
                        video_path,
                        metadata.get('start_time', 0),
                        metadata.get('end_time', time.time())
                    )
                    
                return {
                    'path': video_path,
                    'video_id': video_id
                }
                
            return {'path': video_path}
            
        except Exception as e:
            self.logger.error(f"Error registering video: {e}")
            return None
            
    def retrieve_video(self, video_id):
        """Recuperar video desde su ubicación de almacenamiento"""
        try:
            if not self.video_indexer:
                self.logger.error("No video indexer configured")
                return None
                
            # Obtener detalles del video
            video_details = self.video_indexer.get_video_details(video_id)
            if not video_details:
                return None
                
            # Verificar si el archivo existe localmente
            video_path = video_details['path']
            if os.path.exists(video_path):
                return video_path
                
            # Si el archivo no existe localmente pero está en S3, descargarlo
            if video_path.startswith('s3://') and 's3' in self.storage_backends:
                s3_backend = self.storage_backends['s3']
                local_path = s3_backend.retrieve(video_path)
                
                # Actualizar la ruta en la base de datos
                if local_path:
                    conn = sqlite3.connect(self.video_indexer.db_path)
                    cursor = conn.cursor()
                    cursor.execute('UPDATE videos SET path = ? WHERE id = ?', (local_path, video_id))
                    conn.commit()
                    conn.close()
                    
                return local_path
                
            self.logger.error(f"Video file not found: {video_path}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving video: {e}")
            return None
            
    def cleanup_old_videos(self, retention_policy=None):
        """Limpiar videos antiguos según política de retención"""
        try:
            if not self.video_indexer:
                self.logger.warning("No video indexer configured, skipping cleanup")
                return 0
                
            # Usar política configurada si no se proporciona una
            if retention_policy is None:
                retention_policy = self.config.get('retention_policy', {})
                
            # Valor predeterminado: 30 días
            default_retention = retention_policy.get('default', 30)
            
            # Conexión a la base de datos
            conn = sqlite3.connect(self.video_indexer.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Obtener todos los videos con eventos
            cursor.execute('''
            SELECT v.id, v.path, v.created_at, e.event_type 
            FROM videos v
            LEFT JOIN events e ON v.id = e.video_id
            ''')
            
            rows = cursor.fetchall()
            now = time.time()
            videos_to_delete = []
            
            for row in rows:
                video_id = row['id']
                video_path = row['path']
                created_at = row['created_at']
                event_type = row['event_type']
                
                # Determinar política de retención para este tipo de evento
                days_to_keep = retention_policy.get(event_type, default_retention) if event_type else default_retention
                
                # Calcular tiempo máximo de retención
                max_age = now - (days_to_keep * 86400)  # 86400 segundos = 1 día
                
                # Si el video es más antiguo que el tiempo máximo, marcarlo para eliminación
                if created_at < max_age:
                    videos_to_delete.append((video_id, video_path))
                    
            # Eliminar videos marcados
            deleted_count = 0
            for video_id, video_path in videos_to_delete:
                # Eliminar de la base de datos y el archivo físico
                if self.video_indexer.delete_video(video_id, delete_file=True):
                    deleted_count += 1
                    
            conn.close()
            
            self.logger.info(f"Cleanup completed: {deleted_count} videos deleted")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error in cleanup: {e}")
            return 0
            
    def shutdown(self):
        """Detener actividades en segundo plano"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_event.set()
            self._cleanup_thread.join(timeout=5.0)
            
        self.logger.info("Storage manager shutdown")


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