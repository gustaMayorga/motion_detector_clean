from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseCameraVendor(ABC):
    """Clase base abstracta para integración con diferentes marcas de cámaras"""
    
    def __init__(self):
        self.supported_features = []
        
    @abstractmethod
    def get_stream_url(self, camera_config: Dict[str, Any]) -> str:
        """Obtiene la URL de streaming para la cámara según su configuración"""
        pass
        
    def get_events(self, camera_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Obtiene eventos de la cámara (detección de movimiento, etc.)"""
        # Implementación opcional, no todas las cámaras soportan esto
        return []
        
    def get_device_info(self, camera_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Obtiene información básica del dispositivo"""
        # Implementación opcional
        return None
        
    def ptz_control(self, camera_config: Dict[str, Any], command: str, **kwargs) -> bool:
        """Controla funciones PTZ (Pan/Tilt/Zoom) si la cámara lo soporta"""
        # Implementación opcional
        return False
        
    def get_snapshot(self, camera_config: Dict[str, Any], output_path: Optional[str] = None):
        """Obtiene una imagen instantánea de la cámara"""
        # Implementación opcional
        return None
        
    def is_feature_supported(self, feature: str) -> bool:
        """Verifica si la funcionalidad específica está soportada"""
        return feature in self.supported_features 