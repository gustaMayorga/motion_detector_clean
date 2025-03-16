import json
import logging
import asyncio
import redis.asyncio as redis
from typing import Dict, List, Any, Callable, Awaitable, Optional

class EventBus:
    """
    Sistema de eventos basado en Redis PubSub para vigIA
    Permite comunicación asíncrona entre componentes
    """
    
    def __init__(self, redis_host="localhost", redis_port=6379, 
                 redis_db=0, redis_password=None, retry_on_timeout=True):
        """Inicializa la conexión a Redis y configura el bus de eventos"""
        self.logger = logging.getLogger("EventBus")
        self.redis_config = {
            "host": redis_host,
            "port": redis_port,
            "db": redis_db,
            "password": redis_password,
            "retry_on_timeout": retry_on_timeout,
            "decode_responses": True  # Para recibir strings en vez de bytes
        }
        self.redis = redis.Redis(**self.redis_config)
        self.pubsub = None
        self.handlers: Dict[str, List[Callable[[str, Any], Awaitable[None]]]] = {}
        self.is_running = False
        self.listener_task = None
    
    async def connect(self) -> bool:
        """Establece conexión con Redis"""
        try:
            # Verificar conexión
            await self.redis.ping()
            self.pubsub = self.redis.pubsub()
            self.logger.info("Conexión exitosa a Redis")
            return True
        except redis.ConnectionError as e:
            self.logger.error(f"Error conectando a Redis: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado conectando a Redis: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """Reconecta en caso de pérdida de conexión"""
        self.logger.info("Intentando reconexión a Redis...")
        try:
            # Cerrar conexiones existentes
            if self.pubsub:
                await self.pubsub.close()
            await self.redis.close()
            
            # Crear nuevas conexiones
            self.redis = redis.Redis(**self.redis_config)
            self.pubsub = self.redis.pubsub()
            
            # Verificar conexión
            await self.redis.ping()
            
            # Reactivar suscripciones
            if self.handlers:
                await self.pubsub.subscribe(*self.handlers.keys())
            
            self.logger.info("Reconexión exitosa a Redis")
            return True
        except Exception as e:
            self.logger.error(f"Error durante la reconexión a Redis: {e}")
            return False
    
    async def publish(self, channel: str, message: Any) -> bool:
        """Publica un mensaje en un canal específico"""
        try:
            # Convertir mensaje a JSON si no es string
            if not isinstance(message, str):
                message = json.dumps(message)
            
            # Publicar mensaje
            result = await self.redis.publish(channel, message)
            if result > 0:
                self.logger.debug(f"Mensaje publicado en {channel}, recibido por {result} suscriptores")
            return True
        except redis.ConnectionError:
            self.logger.error("Error de conexión al publicar mensaje, intentando reconectar")
            if await self.reconnect():
                # Reintentar después de reconexión
                return await self.publish(channel, message)
            return False
        except Exception as e:
            self.logger.error(f"Error publicando mensaje: {e}")
            return False
    
    async def subscribe(self, channel: str, handler: Callable[[str, Any], Awaitable[None]]) -> bool:
        """Suscribe a un canal y registra un manejador para los mensajes"""
        try:
            # Inicializar lista de handlers si no existe
            if channel not in self.handlers:
                self.handlers[channel] = []
                # Suscribir al canal en Redis
                if self.pubsub:
                    await self.pubsub.subscribe(channel)
            
            # Registrar handler
            self.handlers[channel].append(handler)
            self.logger.info(f"Suscrito al canal: {channel}")
            
            # Iniciar listener si no está corriendo
            if not self.is_running:
                await self.start_listener()
            
            return True
        except redis.ConnectionError:
            self.logger.error("Error de conexión al suscribirse, intentando reconectar")
            if await self.reconnect():
                # Reintentar después de reconexión
                return await self.subscribe(channel, handler)
            return False
        except Exception as e:
            self.logger.error(f"Error suscribiéndose al canal {channel}: {e}")
            return False
    
    async def unsubscribe(self, channel: str, handler: Optional[Callable] = None) -> bool:
        """Cancela suscripción a un canal específico"""
        try:
            if channel in self.handlers:
                if handler:
                    # Eliminar handler específico
                    self.handlers[channel] = [h for h in self.handlers[channel] if h != handler]
                    # Si no quedan handlers, cancelar suscripción al canal
                    if not self.handlers[channel]:
                        del self.handlers[channel]
                        if self.pubsub:
                            await self.pubsub.unsubscribe(channel)
                else:
                    # Eliminar todos los handlers y cancelar suscripción
                    del self.handlers[channel]
                    if self.pubsub:
                        await self.pubsub.unsubscribe(channel)
                
                self.logger.info(f"Cancelada suscripción al canal: {channel}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error cancelando suscripción al canal {channel}: {e}")
            return False
    
    async def start_listener(self) -> None:
        """Inicia el proceso de escucha de mensajes"""
        if self.is_running:
            return
        
        if not self.pubsub:
            if not await self.connect():
                self.logger.error("No se pudo iniciar listener: conexión a Redis fallida")
                return
        
        # Suscribirse a todos los canales registrados
        if self.handlers:
            await self.pubsub.subscribe(*self.handlers.keys())
        
        self.is_running = True
        self.listener_task = asyncio.create_task(self._message_listener())
        self.logger.info("Iniciado listener de mensajes")
    
    async def stop_listener(self) -> None:
        """Detiene el proceso de escucha de mensajes"""
        self.is_running = False
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
            self.listener_task = None
        
        # Cancelar todas las suscripciones
        if self.pubsub and self.handlers:
            await self.pubsub.unsubscribe(*self.handlers.keys())
        
        self.logger.info("Detenido listener de mensajes")
    
    async def _message_listener(self) -> None:
        """Proceso para escuchar mensajes (loop interno)"""
        try:
            async for message in self.pubsub.listen():
                if not self.is_running:
                    break
                
                # Ignorar mensajes de suscripción/desuscripción
                if message["type"] not in ("message", "pmessage"):
                    continue
                
                channel = message["channel"]
                data = message["data"]
                
                # Procesar mensaje si hay handlers registrados
                if channel in self.handlers:
                    # Convertir de JSON si es posible
                    try:
                        if isinstance(data, str):
                            data = json.loads(data)
                    except json.JSONDecodeError:
                        # No es JSON, usar el mensaje tal cual
                        pass
                    
                    # Ejecutar todos los handlers registrados para este canal
                    for handler in self.handlers[channel]:
                        try:
                            await handler(channel, data)
                        except Exception as e:
                            self.logger.error(f"Error en handler para canal {channel}: {e}")
        
        except redis.ConnectionError:
            self.logger.error("Conexión perdida en el listener, intentando reconectar")
            self.is_running = False
            
            # Intentar reconectar
            if await self.reconnect():
                # Reiniciar listener si reconexión exitosa
                await self.start_listener()
            else:
                self.logger.error("No se pudo reconectar, listener detenido")
        
        except asyncio.CancelledError:
            # Cancelación normal, no es un error
            pass
        
        except Exception as e:
            self.logger.error(f"Error en listener de mensajes: {e}")
            self.is_running = False
    
    async def close(self) -> None:
        """Cierra todas las conexiones y detiene el listener"""
        await self.stop_listener()
        
        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None
        
        if self.redis:
            await self.redis.close()
        
        self.logger.info("EventBus cerrado")

class EventTypes:
    """Constantes para tipos de eventos comunes"""
    OBJECT_DETECTED = "object_detected"
    OBJECT_TRACKED = "object_tracked"
    BEHAVIOR_DETECTED = "behavior_detected"
    ALERT_GENERATED = "alert_generated"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    SYSTEM_ERROR = "system_error"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERIMETER_BREACH = "perimeter_breach"
    THEFT_DETECTED = "theft_detected" 