from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import asyncio
from enum import Enum

class MessagePriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    EMERGENCY = 5

@dataclass
class Message:
    message_id: str
    content: str
    priority: MessagePriority
    recipients: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"
    retries: int = 0

class CommunicationChannel(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 5)
        self._message_queue = asyncio.Queue()
        self._running = False
        
    @abstractmethod
    async def send_message(self, message: Message) -> bool:
        """Envía un mensaje a través del canal"""
        pass
        
    @abstractmethod
    async def format_message(self, message: Message) -> str:
        """Formatea el mensaje según el canal"""
        pass
        
    async def start(self):
        """Inicia el procesamiento de mensajes"""
        self._running = True
        while self._running:
            try:
                message = await self._message_queue.get()
                success = False
                retries = 0
                
                while not success and retries < self.max_retries:
                    success = await self.send_message(message)
                    if not success:
                        retries += 1
                        await asyncio.sleep(self.retry_delay)
                        
                if not success:
                    await self._handle_failed_message(message)
                    
            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                
    async def stop(self):
        """Detiene el procesamiento de mensajes"""
        self._running = False
        
    async def queue_message(self, message: Message):
        """Encola un mensaje para envío"""
        await self._message_queue.put(message)
        
    async def _handle_failed_message(self, message: Message):
        """Maneja mensajes que no pudieron ser enviados"""
        message.status = "failed"
        # Implementar lógica de manejo de fallos
        pass 