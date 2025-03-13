from .communication_base import CommunicationChannel, Message, MessagePriority
import aiohttp
from typing import Dict, Any
import json
from datetime import datetime

class WhatsAppService(CommunicationChannel):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config['api_url']
        self.auth_token = config['auth_token']
        self.templates = config.get('templates', {})
        
    async def send_message(self, message: Message) -> bool:
        """Envía un mensaje por WhatsApp"""
        try:
            formatted_message = await self.format_message(message)
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                }
                
                for recipient in message.recipients:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": recipient,
                        "type": "text",
                        "text": {"body": formatted_message}
                    }
                    
                    async with session.post(
                        self.api_url,
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status != 200:
                            return False
                            
            return True
            
        except Exception as e:
            print(f"Error enviando mensaje WhatsApp: {e}")
            return False
            
    async def format_message(self, message: Message) -> str:
        """Formatea el mensaje según plantillas predefinidas"""
        template = self.templates.get(
            message.metadata.get('template_type', 'default'),
            "{content}"
        )
        
        # Formatear según prioridad
        priority_prefix = {
            MessagePriority.EMERGENCY: "🚨 EMERGENCIA: ",
            MessagePriority.URGENT: "⚠️ URGENTE: ",
            MessagePriority.HIGH: "❗ ",
            MessagePriority.MEDIUM: "",
            MessagePriority.LOW: ""
        }
        
        prefix = priority_prefix.get(message.priority, "")
        formatted_content = template.format(
            content=message.content,
            **message.metadata
        )
        
        return f"{prefix}{formatted_content}" 