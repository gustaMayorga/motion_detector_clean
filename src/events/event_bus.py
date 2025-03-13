import threading
import logging
import time
import queue

class EventBus:
    def __init__(self, async_processing=True):
        self.subscribers = {}
        self.async_processing = async_processing
        self.event_queue = queue.Queue() if async_processing else None
        self.processing_thread = None
        self.logger = logging.getLogger('EventBus')
        self._stop_event = threading.Event()
        
        if async_processing:
            self._start_processing_thread()
            
    def _start_processing_thread(self):
        """Iniciar hilo de procesamiento asíncrono de eventos"""
        self.processing_thread = threading.Thread(
            target=self._process_event_queue,
            daemon=True
        )
        self.processing_thread.start()
        
    def _process_event_queue(self):
        """Procesar eventos en cola de forma continua"""
        while not self._stop_event.is_set():
            try:
                event_type, data = self.event_queue.get(timeout=0.1)
                self._dispatch_event(event_type, data)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                
    def _dispatch_event(self, event_type, data):
        """Entregar evento a todos los suscriptores"""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"Error in subscriber callback: {e}")
                    
    def subscribe(self, event_type, callback):
        """Suscribir callback a un tipo de evento específico"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        return lambda: self.unsubscribe(event_type, callback)
        
    def unsubscribe(self, event_type, callback):
        """Cancelar suscripción de un callback"""
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            if not self.subscribers[event_type]:
                del self.subscribers[event_type]
                
    def publish(self, event_type, data):
        """Publicar un evento"""
        if self.async_processing:
            self.event_queue.put((event_type, data))
        else:
            self._dispatch_event(event_type, data)
            
    def shutdown(self):
        """Detener procesamiento de eventos"""
        if self.async_processing:
            self._stop_event.set()
            if self.processing_thread:
                self.processing_thread.join(timeout=2.0)
                
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