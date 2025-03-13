from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NotificationConfig:
    enabled: bool
    credentials: Dict[str, str]
    templates: Dict[str, str]
    retry_count: int = 3
    retry_delay: int = 5  # segundos

class NotificationChannel(ABC):
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.last_error = None
        
    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> bool:
        """Envía una notificación"""
        pass
        
    @abstractmethod
    def format_message(self, data: Dict[str, Any]) -> str:
        """Formatea el mensaje según el canal"""
        pass
        
    async def handle_error(self, error: Exception):
        """Maneja errores de envío"""
        self.last_error = {
            'timestamp': datetime.now(),
            'error': str(error),
            'type': type(error).__name__
        } 

class NotificationService(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    @abstractmethod
    async def send_notification(self, message: str, data: Dict[str, Any] = None):
        """Envía una notificación"""
        pass
        
    async def send_alert(self, alert_type: str, details: Dict[str, Any]):
        """Envía una alerta"""
        message = f"ALERTA: {alert_type}"
        data = {
            "type": alert_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_notification(message, data) 