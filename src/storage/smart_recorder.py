from collections import deque
import cv2
import os
import time
import logging
import threading
import numpy as np
from datetime import datetime

class SmartRecorder:
    def __init__(self, config_path="configs/storage.json", storage_manager=None):
        self.config = self._load_config(config_path)
        self.pre_event_buffer_size = self.config.get("pre_event_buffer", 300)  # frames
        self.buffers = {}  # Camera ID -> deque of frames
        self.recording_sessions = {}  # Session ID -> recording info
        self.logger = logging.getLogger('SmartRecorder')
        self.storage_manager = storage_manager
        self.lock = threading.RLock()
        
    def _load_config(self, config_path):
        """Cargar configuración desde archivo JSON"""
        if not os.path.exists(config_path):
            return {
                "pre_event_buffer": 300,  # frames (10 segundos a 30 fps)
                "post_event_buffer": 150,  # frames (5 segundos a 30 fps)
                "default_recording_duration": 60,  # segundos
                "output_directory": "recordings",
                "codec": "mp4v",
                "quality": 95,
                "resolution": null  # Mantener resolución original
            }
            
        import json
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading storage config: {e}")
            return {}
            
    def initialize_camera(self, camera_id, fps=30.0):
        """Inicializar buffer para una cámara"""
        with self.lock:
            if camera_id not in self.buffers:
                self.buffers[camera_id] = {
                    'frames': deque(maxlen=self.pre_event_buffer_size),
                    'fps': fps
                }
                self.logger.info(f"Initialized buffer for camera {camera_id}")
                
    def add_frame(self, camera_id, frame, timestamp=None, metadata=None):
        """Añadir frame al buffer temporal de una cámara"""
        if timestamp is None:
            timestamp = time.time()
            
        if metadata is None:
            metadata = {}
            
        # Asegurar que existe el buffer para esta cámara
        if camera_id not in self.buffers:
            self.initialize_camera(camera_id)
            
        # Añadir frame al buffer
        with self.lock:
            buffer = self.buffers[camera_id]['frames']
            buffer.append({
                'frame': frame.copy(),
                'timestamp': timestamp,
                'metadata': metadata
            })
            
        # Procesar grabaciones activas para esta cámara
        self._process_active_recordings(camera_id, frame, timestamp, metadata)
        
    def _process_active_recordings(self, camera_id, frame, timestamp, metadata):
        """Procesar grabaciones activas para una cámara"""
        with self.lock:
            # Identificar grabaciones activas para esta cámara
            active_sessions = [
                session_id for session_id, session in self.recording_sessions.items()
                if session['camera_id'] == camera_id and session['active']
            ]
            
            # Agregar frame a cada grabación activa
            for session_id in active_sessions:
                session = self.recording_sessions[session_id]
                
                # Agregar frame a grabadora
                session['writer'].write(frame)
                session['frame_count'] += 1
                session['last_frame_time'] = timestamp
                
                # Verificar si la grabación ha alcanzado su duración máxima
                if session['duration'] and timestamp - session['start_time'] >= session['duration']:
                    self._finish_recording(session_id)
                    
    def start_recording(self, camera_id, event_id, event_type, duration=None, pre_event=10):
        """Iniciar grabación con pre-buffer de eventos"""
        with self.lock:
            # Verificar que la cámara existe
            if camera_id not in self.buffers:
                self.logger.error(f"Camera {camera_id} not initialized")
                return None
                
            # Crear ID de sesión único
            session_id = f"{camera_id}_{event_id}_{int(time.time())}"
            
            # Obtener directorio de salida
            output_dir = self.config.get("output_directory", "recordings")
            os.makedirs(output_dir, exist_ok=True)
            
            # Crear nombre de archivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{output_dir}/{camera_id}_{event_type}_{timestamp}.mp4"
            
            # Obtener información del buffer
            buffer = self.buffers[camera_id]['frames']
            fps = self.buffers[camera_id]['fps']
            
            # Si el buffer está vacío, no podemos iniciar grabación
            if not buffer:
                self.logger.warning(f"Buffer empty for camera {camera_id}")
                return None
                
            # Obtener un frame para determinar tamaño
            sample_frame = buffer[0]['frame']
            height, width = sample_frame.shape[:2]
            
            # Verificar si necesitamos cambiar la resolución
            target_resolution = self.config.get("resolution")
            if target_resolution:
                width, height = target_resolution
                
            # Configurar codec de video
            fourcc = cv2.VideoWriter_fourcc(*self.config.get("codec", "mp4v"))
            out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
            
            # Escribir frames del pre-buffer
            now = time.time()
            pre_event_time = now - pre_event  # Tiempo desde hace N segundos
            
            for item in buffer:
                if item['timestamp'] >= pre_event_time:
                    # Redimensionar si es necesario
                    if target_resolution:
                        frame = cv2.resize(item['frame'], (width, height))
                    else:
                        frame = item['frame']
                    out.write(frame)
                    
            # Crear entrada para la sesión de grabación
            self.recording_sessions[session_id] = {
                'camera_id': camera_id,
                'event_id': event_id,
                'event_type': event_type,
                'filename': filename,
                'writer': out,
                'start_time': now,
                'duration': duration,  # None significa grabar hasta stop_recording
                'active': True,
                'frame_count': len([item for item in buffer if item['timestamp'] >= pre_event_time]),
                'last_frame_time': now
            }
            
            self.logger.info(f"Started recording session {session_id} for event {event_id}")
            return session_id
            
    def stop_recording(self, session_id):
        """Finalizar grabación y almacenar video resultante"""
        with self.lock:
            return self._finish_recording(session_id)
            
    def _finish_recording(self, session_id):
        """Finalizar grabación y liberar recursos"""
        if session_id not in self.recording_sessions:
            self.logger.error(f"Recording session {session_id} not found")
            return False
            
        session = self.recording_sessions[session_id]
        
        if not session['active']:
            self.logger.warning(f"Recording session {session_id} already finished")
            return False
            
        # Liberar escritor de video
        session['writer'].release()
        session['active'] = False
        session['end_time'] = time.time()
        
        # Calcular duración real
        duration = session['end_time'] - session['start_time']
        
        # Guardar información de metadatos
        metadata = {
            'camera_id': session['camera_id'],
            'event_id': session['event_id'],
            'event_type': session['event_type'],
            'start_time': session['start_time'],
            'end_time': session['end_time'],
            'duration': duration,
            'frame_count': session['frame_count'],
            'filename': session['filename']
        }
        
        # Si tenemos storage_manager, registrar el video
        if self.storage_manager:
            self.storage_manager.register_video(session['filename'], metadata)
            
        self.logger.info(f"Finished recording session {session_id}, duration: {duration:.2f}s, frames: {session['frame_count']}")
        
        return {
            'filename': session['filename'],
            'metadata': metadata
        }
        
    def get_active_recordings(self):
        """Obtener lista de grabaciones activas"""
        with self.lock:
            return {
                session_id: {
                    'camera_id': session['camera_id'],
                    'event_id': session['event_id'],
                    'event_type': session['event_type'],
                    'start_time': session['start_time'],
                    'filename': session['filename'],
                    'frame_count': session['frame_count']
                }
                for session_id, session in self.recording_sessions.items()
                if session['active']
            }
            
    def stop_all_recordings(self):
        """Detener todas las grabaciones activas"""
        with self.lock:
            active_sessions = [
                session_id for session_id, session in self.recording_sessions.items()
                if session['active']
            ]
            
            results = {}
            for session_id in active_sessions:
                results[session_id] = self._finish_recording(session_id)
                
            return results
            
    def cleanup(self):
        """Limpiar recursos y detener grabaciones"""
        results = self.stop_all_recordings()
        
        with self.lock:
            self.buffers.clear()
            
        return results