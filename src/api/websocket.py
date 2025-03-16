import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional, Callable, Awaitable
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
from starlette.websockets import WebSocketState

from src.events.event_bus import EventBus
from src.database.db import get_db
from src.database.models import User, Camera
# from src.api.auth import get_current_user_ws

class ConnectionManager:
    """Gestiona conexiones WebSocket para transmisión en tiempo real"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        self.logger = logging.getLogger("WebSocketManager")
        
    async def connect(self, websocket: WebSocket, channel: str, user_id: int = None):
        """Establece una conexión WebSocket"""
        await websocket.accept()
        
        # Inicializar canal si no existe
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        
        # Añadir conexión al canal
        self.active_connections[channel].add(websocket)
        
        # Registrar conexión de usuario si se proporciona ID
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
            
        self.logger.info(f"Nueva conexión WebSocket: canal={channel}, usuario={user_id}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = None, user_id: int = None):
        """Desconecta un WebSocket"""
        # Eliminar de todos los canales si no se especifica uno
        if channel:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
                # Eliminar canal si está vacío
                if not self.active_connections[channel]:
                    del self.active_connections[channel]
        else:
            # Buscar en todos los canales
            for ch in list(self.active_connections.keys()):
                if websocket in self.active_connections[ch]:
                    self.active_connections[ch].discard(websocket)
                    # Eliminar canal si está vacío
                    if not self.active_connections[ch]:
                        del self.active_connections[ch]
        
        # Eliminar conexión de usuario
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        elif not user_id:
            # Buscar en todos los usuarios
            for uid in list(self.user_connections.keys()):
                if websocket in self.user_connections[uid]:
                    self.user_connections[uid].discard(websocket)
                    if not self.user_connections[uid]:
                        del self.user_connections[uid]
        
        self.logger.info(f"Conexión WebSocket cerrada: canal={channel}, usuario={user_id}")
    
    async def send_message(self, message: Any, channel: str):
        """Envía un mensaje a todos los clientes en un canal"""
        if channel not in self.active_connections:
            return
        
        # Convertir a JSON si no es string
        if not isinstance(message, str):
            message = json.dumps(message)
        
        # Enviar a todas las conexiones en el canal
        disconnected = set()
        for connection in self.active_connections[channel]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
            except RuntimeError:
                # Conexión cerrada o inválida
                disconnected.add(connection)
            except Exception as e:
                self.logger.error(f"Error enviando mensaje WebSocket: {e}")
                disconnected.add(connection)
        
        # Eliminar conexiones desconectadas
        for conn in disconnected:
            await self.disconnect(conn, channel)
    
    async def broadcast(self, message: Any):
        """Envía un mensaje a todos los clientes en todos los canales"""
        # Convertir a JSON si no es string
        if not isinstance(message, str):
            message = json.dumps(message)
            
        all_connections = set()
        for connections in self.active_connections.values():
            all_connections.update(connections)
        
        # Enviar a todas las conexiones únicas
        disconnected = set()
        for connection in all_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
            except RuntimeError:
                # Conexión cerrada o inválida
                disconnected.add(connection)
            except Exception as e:
                self.logger.error(f"Error en broadcast WebSocket: {e}")
                disconnected.add(connection)
        
        # Eliminar conexiones desconectadas
        for conn in disconnected:
            await self.disconnect(conn)
    
    async def send_to_user(self, user_id: int, message: Any):
        """Envía un mensaje a todas las conexiones de un usuario"""
        if user_id not in self.user_connections:
            return
        
        # Convertir a JSON si no es string
        if not isinstance(message, str):
            message = json.dumps(message)
        
        # Enviar a todas las conexiones del usuario
        disconnected = set()
        for connection in self.user_connections[user_id]:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
            except RuntimeError:
                # Conexión cerrada o inválida
                disconnected.add(connection)
            except Exception as e:
                self.logger.error(f"Error enviando mensaje a usuario {user_id}: {e}")
                disconnected.add(connection)
        
        # Eliminar conexiones desconectadas
        for conn in disconnected:
            await self.disconnect(conn, user_id=user_id)

# Instancia global de ConnectionManager
manager = ConnectionManager()

# Manejador de eventos del EventBus para WebSockets
class WebSocketEventHandler:
    """Maneja eventos del sistema y los envía a los clientes WebSocket"""
    
    def __init__(self, event_bus: EventBus, connection_manager: ConnectionManager):
        self.event_bus = event_bus
        self.manager = connection_manager
        self.logger = logging.getLogger("WebSocketEventHandler")
        self.subscriptions = {}
    
    async def initialize(self):
        """Inicializa las suscripciones a eventos"""
        # Lista de canales a los que suscribirse
        channels = [
            "alert_*",  # Todos los eventos de alertas
            "camera_*",  # Todos los eventos de cámaras
            "detection_*",  # Todos los eventos de detección
            "system_*",  # Todos los eventos del sistema
            "user_*",  # Todos los eventos de usuarios
        ]
        
        # Suscribirse a cada canal
        for channel in channels:
            await self.event_bus.subscribe(channel, self.handle_event)
            self.subscriptions[channel] = True
        
        # Iniciar listener
        await self.event_bus.start_listener()
        self.logger.info("Iniciado manejador de eventos para WebSockets")
    
    async def handle_event(self, channel: str, data: Any):
        """Maneja un evento recibido y lo reenvía a los clientes WebSocket"""
        try:
            # Determinar el canal WebSocket según el canal de eventos
            ws_channel = channel.replace("_", "/")
            
            # Añadir timestamp si no existe
            if isinstance(data, dict) and "timestamp" not in data:
                data["timestamp"] = datetime.now().isoformat()
            
            # Enviar mensaje a través del connection manager
            await self.manager.send_message(data, ws_channel)
            
            # Si es una alerta, también enviar al canal general de alertas
            if channel.startswith("alert_"):
                await self.manager.send_message(data, "alerts")
            
            # Si es un evento de sistema, también enviar al canal general de sistema
            if channel.startswith("system_"):
                await self.manager.send_message(data, "system")
            
            self.logger.debug(f"Evento reenviado a WebSockets: {channel}")
            
        except Exception as e:
            self.logger.error(f"Error manejando evento para WebSockets: {e}")
    
    async def close(self):
        """Cierra el manejador de eventos"""
        # Detener listener
        await self.event_bus.stop_listener()
        
        # Cancelar suscripciones
        for channel in self.subscriptions:
            await self.event_bus.unsubscribe(channel, self.handle_event)
        
        self.subscriptions = {}
        self.logger.info("Cerrado manejador de eventos para WebSockets") 