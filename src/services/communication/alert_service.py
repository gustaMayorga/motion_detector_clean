from typing import Dict, Any, List
from datetime import datetime
import asyncio
from .communication_base import Message, MessagePriority
from .whatsapp_service import WhatsAppService

class AlertService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels = self._initialize_channels()
        self.alert_levels = {
            "info": MessagePriority.LOW,
            "warning": MessagePriority.MEDIUM,
            "alert": MessagePriority.HIGH,
            "critical": MessagePriority.URGENT,
            "emergency": MessagePriority.EMERGENCY
        }
        
    def _initialize_channels(self) -> Dict[str, Any]:
        """Inicializa los canales de comunicación"""
        channels = {}
        
        if self.config.get('whatsapp', {}).get('enabled', False):
            channels['whatsapp'] = WhatsAppService(
                self.config['whatsapp']
            )
            
        # Añadir más canales aquí
        
        return channels
        
    async def start(self):
        """Inicia todos los canales de comunicación"""
        for channel in self.channels.values():
            asyncio.create_task(channel.start())
            
    async def stop(self):
        """Detiene todos los canales de comunicación"""
        for channel in self.channels.values():
            await channel.stop()
            
    async def send_alert(self, 
                        alert_type: str,
                        message: str,
                        recipients: List[str],
                        metadata: Dict[str, Any] = None):
        """Envía una alerta por todos los canales configurados"""
        priority = self.alert_levels.get(alert_type, MessagePriority.MEDIUM)
        
        alert_message = Message(
            message_id=f"alert_{datetime.now().timestamp()}",
            content=message,
            priority=priority,
            recipients=recipients,
            metadata=metadata or {},
            timestamp=datetime.now()
        )
        
        # Enviar por todos los canales activos
        for channel in self.channels.values():
            await channel.queue_message(alert_message)

    def format_alert(self, alert_type, data):
        """Formatea la alerta según el canal""" 