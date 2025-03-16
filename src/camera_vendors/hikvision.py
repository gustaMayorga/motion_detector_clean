import requests
import cv2
from src.camera_vendors.base import BaseCameraVendor

class HikvisionVendor(BaseCameraVendor):
    """Integración con cámaras Hikvision"""
    
    def __init__(self):
        self.supported_features = ["rtsp", "ptz", "events", "config"]
        
    def get_stream_url(self, camera_config):
        ip = camera_config['ip']
        username = camera_config['username']
        password = camera_config['password']
        channel = camera_config.get('channel', 1)
        stream = camera_config.get('stream', 0)
        
        return f"rtsp://{username}:{password}@{ip}:554/h264/ch{channel}/{stream}"
        
    def get_events(self, camera_config):
        """Obtener eventos de la cámara (detección de movimiento, etc.)"""
        # Implementación usando ISAPI
        # ... 