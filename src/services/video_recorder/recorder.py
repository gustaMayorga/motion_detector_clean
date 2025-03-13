from typing import Dict, List, Any, Optional
import cv2
import numpy as np
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, field
import shutil
import os

@dataclass
class RecordingMetadata:
    start_time: datetime
    end_time: Optional[datetime]
    trigger_type: str
    camera_id: str
    file_path: str
    file_size: int
    duration: float
    resolution: tuple
    fps: float
    events: List[Dict[str, Any]] = field(default_factory=list)

class VideoRecorder:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_recordings: Dict[str, Dict[str, Any]] = {}
        
    async def start_recording(
        self, camera_id: str, trigger_type: str, frame: Optional[Any] = None
    ) -> str:
        """Inicia una grabación"""
        # Crear nombre único para la grabación
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_id = f"{camera_id}_{timestamp}"
        
        # Crear directorio de almacenamiento
        storage_path = Path(self.config['storage_path'])
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Crear archivo de video
        video_path = storage_path / f"{recording_id}.mp4"
        
        # Obtener dimensiones del frame
        if frame is not None:
            height, width = frame.shape[:2]
        else:
            height, width = 480, 640  # Valores predeterminados
            
        # Crear escritor de video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = self.config.get('fps', 20)
        
        writer = cv2.VideoWriter(
            str(video_path),
            fourcc,
            fps,
            (width, height)
        )
        
        # Crear metadatos
        metadata = {
            'recording_id': recording_id,
            'camera_id': camera_id,
            'start_time': datetime.now().isoformat(),
            'trigger_type': trigger_type,
            'events': []
        }
        
        # Almacenar información de la grabación
        self.active_recordings[recording_id] = {
            'writer': writer,
            'metadata': metadata,
            'frame_count': 0,
            'start_time': datetime.now()
        }
        
        # Escribir primer frame si está disponible
        if frame is not None:
            writer.write(frame)
            self.active_recordings[recording_id]['frame_count'] += 1
            
        return recording_id
        
    async def add_frame(
        self, recording_id: str, frame: Any, events: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Añade un frame a la grabación"""
        if recording_id not in self.active_recordings:
            return False
            
        recording = self.active_recordings[recording_id]
        
        # Añadir frame
        recording['writer'].write(frame)
        recording['frame_count'] += 1
        
        # Añadir eventos
        if events:
            recording['metadata']['events'].extend(events)
            
        # Verificar duración máxima
        if self.config.get('max_duration_minutes'):
            elapsed = (datetime.now() - recording['start_time']).total_seconds() / 60
            if elapsed >= self.config['max_duration_minutes']:
                await self.stop_recording(recording_id)
                return False
                
        return True
        
    async def stop_recording(self, recording_id: str) -> bool:
        """Detiene una grabación"""
        if recording_id not in self.active_recordings:
            return False
            
        recording = self.active_recordings[recording_id]
        
        # Liberar escritor de video
        recording['writer'].release()
        
        # Actualizar metadatos
        recording['metadata']['end_time'] = datetime.now().isoformat()
        recording['metadata']['frame_count'] = recording['frame_count']
        
        # Guardar metadatos
        storage_path = Path(self.config['storage_path'])
        metadata_path = storage_path / f"{recording_id}_metadata.json"
        
        with open(metadata_path, 'w') as f:
            json.dump(recording['metadata'], f, indent=2)
            
        # Eliminar grabación activa
        del self.active_recordings[recording_id]
        
        return True
        
    async def get_recording_metadata(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene los metadatos de una grabación"""
        # Verificar si es una grabación activa
        if recording_id in self.active_recordings:
            return self.active_recordings[recording_id]['metadata'].copy()
            
        # Verificar si existe archivo de metadatos
        storage_path = Path(self.config['storage_path'])
        metadata_path = storage_path / f"{recording_id}_metadata.json"
        
        if not metadata_path.exists():
            return None
            
        # Cargar metadatos
        with open(metadata_path, 'r') as f:
            return json.load(f)
            
    async def clean_old_recordings(self, max_age_days: int = 30) -> int:
        """Limpia grabaciones antiguas"""
        storage_path = Path(self.config['storage_path'])
        if not storage_path.exists():
            return 0
            
        # Obtener fecha límite
        limit_date = datetime.now().timestamp() - (max_age_days * 86400)
        
        # Contar eliminados
        deleted_count = 0
        
        # Listar archivos
        for file_path in storage_path.glob('*.mp4'):
            # Obtener fecha de modificación
            mod_time = os.path.getmtime(file_path)
            
            # Eliminar si es antiguo
            if mod_time < limit_date:
                # Eliminar archivo de video
                file_path.unlink()
                
                # Eliminar metadatos si existen
                metadata_path = file_path.with_name(f"{file_path.stem}_metadata.json")
                if metadata_path.exists():
                    metadata_path.unlink()
                    
                deleted_count += 1
                
        return deleted_count 