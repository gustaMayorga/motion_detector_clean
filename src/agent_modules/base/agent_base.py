from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
from src.utils.logging import SecurityLogger
from src.core.event_system import EventBus, Event

@dataclass
class AgentConfig:
    name: str
    type: str
    enabled: bool = True
    settings: Dict[str, Any] = None

@dataclass
class AgentStatus:
    status: str
    last_update: datetime
    details: Dict[str, Any]

class BaseAgent(ABC):
    def __init__(self, config: Dict[str, Any], event_bus: EventBus, logger: SecurityLogger):
        self.config = config
        self.event_bus = event_bus
        self.logger = logger
        self.status = AgentStatus(
            status="initialized",
            last_update=datetime.now(),
            details={}
        )
        self.running = False
        self._processing_lock = asyncio.Lock()
        
    async def start(self):
        """Inicia el agente"""
        self.running = True
        await self.logger.log_event(
            'agent_started',
            {'agent_name': self.config['name']}
        )
        await self.update_status("running")
        
    async def stop(self):
        """Detiene el agente"""
        self.running = False
        await self.logger.log_event(
            'agent_stopped',
            {'agent_name': self.config['name']}
        )
        await self.update_status("stopped")
        
    async def update_status(self, status: str, details: Dict[str, Any] = None):
        """Actualiza el estado del agente"""
        self.status = AgentStatus(
            status=status,
            last_update=datetime.now(),
            details=details or {}
        )
        
        # Emitir evento de cambio de estado
        await self.emit_event(
            "agent_status_changed",
            {
                "agent_id": self.config['name'],
                "status": status,
                "details": details or {}
            }
        )
        
    async def emit_event(self, event_type: str, data: Dict[str, Any], priority: int = 1):
        """Emite un evento al bus de eventos"""
        event = Event(
            event_type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=self.config['name'],
            priority=priority
        )
        
        await self.event_bus.emit(event)
        
    async def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Maneja errores del agente"""
        await self.logger.log_error(error, {
            'agent_name': self.config['name'],
            'agent_type': self.config['type'],
            **(context or {})
        })
        error_context = {"error": str(error)}
        if context:
            error_context.update(context)
        await self.update_status("error", error_context)
        
    @abstractmethod
    async def process_frame(self, frame, frame_id: int):
        """Procesa un frame de video"""
        pass
        
    async def validate_config(self) -> bool:
        """Valida la configuración del agente"""
        required_fields = ['name', 'type', 'enabled']
        
        for field in required_fields:
            if field not in self.config:
                await self.handle_error(
                    ValueError(f"Campo requerido faltante: {field}"),
                    {"config": self.config}
                )
                return False
                
        return True
        
    async def _safe_process(self, func, *args, **kwargs):
        """Ejecuta una función de manera segura con manejo de errores"""
        try:
            async with self._processing_lock:
                return await func(*args, **kwargs)
        except Exception as e:
            await self.handle_error(e, {
                "function": func.__name__,
                "args": args,
                "kwargs": kwargs
            })
            return None 