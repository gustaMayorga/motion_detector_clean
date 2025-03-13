from typing import Dict, Any, List, Callable, Awaitable, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json
from pathlib import Path

@dataclass
class Event:
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime
    source: str
    priority: int = 1
    id: Optional[str] = None

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        self.event_history: List[Event] = []
        self.max_history = 1000
        self._lock = asyncio.Lock()
        
    async def emit(self, event: Event):
        """Emite un evento a todos los suscriptores"""
        if event.event_type in self.subscribers:
            for callback in self.subscribers[event.event_type]:
                await callback(event)
                
    def subscribe(self, event_type: str, callback: Callable[[Event], Awaitable[None]]):
        """Suscribe un callback a un tipo de evento"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        
    def unsubscribe(self, event_type: str, callback: Callable):
        """Desuscribe un callback de un tipo de evento"""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
            
    async def _safe_callback(self, callback: Callable, event: Event):
        """Ejecuta un callback de manera segura"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            print(f"Error en callback de evento {event.event_type}: {e}")
            
    def get_recent_events(self, event_type: Optional[str] = None, 
                         limit: int = 100) -> List[Event]:
        """Obtiene eventos recientes del historial"""
        if event_type:
            events = [e for e in self.event_history if e.event_type == event_type]
        else:
            events = self.event_history.copy()
            
        return sorted(events, 
                     key=lambda x: x.timestamp, 
                     reverse=True)[:limit]
                     
    async def save_events(self, path: Path):
        """Guarda eventos en disco"""
        async with self._lock:
            events_data = [
                {
                    'event_type': e.event_type,
                    'data': e.data,
                    'timestamp': e.timestamp.isoformat(),
                    'source': e.source,
                    'priority': e.priority,
                    'id': e.id
                }
                for e in self.event_history
            ]
            
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(events_data, f, indent=2) 