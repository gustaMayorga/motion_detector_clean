import os
import logging
import subprocess
import threading
import queue
from gtts import gTTS
from playsound import playsound

class ActiveResponseManager:
    """Gestiona respuestas activas a eventos detectados"""
    
    def __init__(self, config=None):
        """
        Inicializa el gestor de respuestas activas
        
        Args:
            config: Configuración para respuestas automáticas
        """
        self.logger = logging.getLogger('ActiveResponseManager')
        self.config = config or {}
        self.message_queue = queue.Queue()
        self.enabled = self.config.get('enabled', True)
        self.response_thread = None
        self.running = False
        
        # Audio cacheado para mensajes comunes
        self.audio_cache = {}
        
        # Iniciar procesamiento en segundo plano
        self.start()
        
    def start(self):
        """Iniciar procesamiento en segundo plano"""
        if not self.running:
            self.running = True
            self.response_thread = threading.Thread(target=self._process_responses)
            self.response_thread.daemon = True
            self.response_thread.start()
            self.logger.info("Gestor de respuestas activas iniciado")
            
    def stop(self):
        """Detener procesamiento"""
        self.running = False
        if self.response_thread:
            self.response_thread.join(timeout=2.0)
            self.response_thread = None
        self.logger.info("Gestor de respuestas activas detenido")
        
    def _process_responses(self):
        """Procesar respuestas en segundo plano"""
        while self.running:
            try:
                # Obtener siguiente mensaje de la cola
                response_data = self.message_queue.get(timeout=1.0)
                
                # Procesar según tipo
                response_type = response_data.get('type')
                if response_type == 'audio':
                    self._process_audio_message(response_data)
                elif response_type == 'light':
                    self._process_light_signal(response_data)
                elif response_type == 'command':
                    self._process_external_command(response_data)
                
                self.message_queue.task_done()
                
            except queue.Empty:
                pass
            except Exception as e:
                self.logger.error(f"Error al procesar respuesta: {e}")
                
    def _process_audio_message(self, data):
        """Reproducir mensaje de audio"""
        message = data.get('message', '')
        language = data.get('language', 'es')
        device = data.get('device', 'default')
        
        try:
            # Verificar si está en caché
            cache_key = f"{message}-{language}"
            audio_file = self.audio_cache.get(cache_key)
            
            if not audio_file or not os.path.exists(audio_file):
                # Crear archivo de audio
                tts = gTTS(text=message, lang=language, slow=False)
                
                # Guardar en directorio temporal
                os.makedirs('temp/audio', exist_ok=True)
                audio_file = f"temp/audio/message_{hash(cache_key)}.mp3"
                tts.save(audio_file)
                
                # Guardar en caché
                self.audio_cache[cache_key] = audio_file
                
            # Reproducir audio
            if device == 'default':
                playsound(audio_file)
            else:
                # Usar dispositivo específico (implementación depende del sistema)
                self._play_on_device(audio_file, device)
                
            self.logger.info(f"Mensaje de audio reproducido: '{message}'")
            
        except Exception as e:
            self.logger.error(f"Error al reproducir mensaje de audio: {e}")
            
    def _play_on_device(self, audio_file, device):
        """Reproducir en dispositivo específico"""
        # Implementación depende del sistema operativo y hardware
        pass
            
    def _process_light_signal(self, data):
        """Activar señal luminosa"""
        # Implementación depende del hardware disponible
        pass
        
    def _process_external_command(self, data):
        """Ejecutar comando externo"""
        command = data.get('command', '')
        
        try:
            if command:
                subprocess.run(command, shell=True, check=True)
                self.logger.info(f"Comando ejecutado: '{command}'")
        except Exception as e:
            self.logger.error(f"Error al ejecutar comando: {e}")
            
    def queue_audio_warning(self, message, event_data=None, language='es', device='default'):
        """
        Encolar advertencia de audio
        
        Args:
            message: Mensaje a reproducir
            event_data: Datos del evento que activó la advertencia
            language: Código de idioma
            device: Dispositivo de salida
        """
        if not self.enabled:
            return False
            
        # Personalizar mensaje según evento
        if event_data and not message:
            event_type = event_data.get('type')
            if event_type == 'intrusion':
                zone = event_data.get('zone', 'esta área')
                message = f"Atención. Ha sido detectado en {zone}. Esta es una zona restringida."
            elif event_type == 'loitering':
                message = "Atención. Su comportamiento está siendo monitoreado. Por favor, continúe su camino."
            elif event_type == 'tailgating':
                message = "Atención. Acceso no autorizado detectado. El personal de seguridad ha sido alertado."
            else:
                message = "Atención. Su actividad está siendo monitoreada por el sistema de seguridad."
        
        # Encolar mensaje
        self.message_queue.put({
            'type': 'audio',
            'message': message,
            'language': language,
            'device': device,
            'event': event_data
        })
        
        return True 