from .notification_base import NotificationChannel, NotificationConfig
import aiohttp
from typing import Dict, Any
import json

class WhatsAppService(NotificationChannel):
    def __init__(self, config: NotificationConfig):
        super().__init__(config)
        self.api_url = "https://graph.facebook.com/v17.0/"
        self.headers = {
            "Authorization": f"Bearer {self.config.credentials['access_token']}",
            "Content-Type": "application/json"
        }
        
    async def send(self, message: Dict[str, Any]) -> bool:
        """Envía mensaje por WhatsApp"""
        formatted_message = self.format_message(message)
        
        payload = {
            "messaging_product": "whatsapp",
            "to": message['recipient'],
            "type": "text",
            "text": {"body": formatted_message}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}{self.config.credentials['phone_number_id']}/messages",
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        error_data = await response.json()
                        await self.handle_error(Exception(f"WhatsApp API error: {error_data}"))
                        return False
                        
        except Exception as e:
            await self.handle_error(e)
            return False
            
    def format_message(self, data: Dict[str, Any]) -> str:
        """Formatea el mensaje para WhatsApp"""
        template = self.config.templates.get(data['type'], self.config.templates['default'])
        
        # Formatear mensaje según el tipo de alerta
        if data['type'] == 'suspicious_behavior':
            return template.format(
                location=data['location'],
                behavior=data['behavior'],
                confidence=f"{data['confidence']*100:.1f}%",
                time=data['timestamp']
            )
        
        return template.format(**data) 