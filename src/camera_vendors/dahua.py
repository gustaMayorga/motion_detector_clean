import requests
import cv2
import json
import logging
import time
import base64
from urllib.parse import quote
from src.camera_vendors.base import BaseCameraVendor

class DahuaVendor(BaseCameraVendor):
    """Integración con cámaras Dahua"""
    
    def __init__(self):
        self.supported_features = ["rtsp", "ptz", "events", "config", "recordings"]
        self.logger = logging.getLogger("DahuaVendor")
        self.sessions = {}  # Almacena sesiones activas por cámara
    
    def get_stream_url(self, camera_config):
        """Obtiene URL para stream RTSP de cámara Dahua"""
        ip = camera_config['ip']
        username = camera_config['username']
        password = camera_config['password']
        channel = camera_config.get('channel', 1)
        stream = camera_config.get('stream', 'main')  # 'main', 'sub', 'snap'
        
        # Codificar credenciales para URL
        auth = f"{quote(username)}:{quote(password)}"
        
        return f"rtsp://{auth}@{ip}:554/cam/realmonitor?channel={channel}&subtype={stream}"
    
    def connect(self, camera_config):
        """Establece conexión con la cámara y guarda la sesión"""
        ip = camera_config['ip']
        username = camera_config['username']
        password = camera_config['password']
        http_port = camera_config.get('http_port', 80)
        
        # URL base para API
        base_url = f"http://{ip}:{http_port}/cgi-bin"
        
        try:
            # Autenticar y obtener sesión
            auth_url = f"{base_url}/global.cgi?action=login&username={username}&password={password}"
            response = requests.get(auth_url, timeout=5)
            
            if response.status_code != 200 or "Error" in response.text:
                self.logger.error(f"Error de autenticación en cámara Dahua {ip}: {response.text}")
                return False
            
            # Extraer ID de sesión
            session_line = [line for line in response.text.split('\n') if 'session' in line.lower()]
            if not session_line:
                self.logger.error(f"No se encontró ID de sesión en la respuesta: {response.text}")
                return False
            
            session_id = session_line[0].split('=')[1].strip()
            
            # Guardar sesión
            self.sessions[ip] = {
                'id': session_id,
                'base_url': base_url,
                'last_used': time.time()
            }
            
            self.logger.info(f"Conexión establecida con cámara Dahua {ip}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error conectando con cámara Dahua {ip}: {e}")
            return False
    
    def get_device_info(self, camera_config):
        """Obtiene información básica del dispositivo"""
        ip = camera_config['ip']
        
        # Asegurar que hay conexión
        if ip not in self.sessions:
            if not self.connect(camera_config):
                return None
        
        session = self.sessions[ip]
        base_url = session['base_url']
        session_id = session['id']
        
        try:
            # Consultar información del dispositivo
            info_url = f"{base_url}/magicBox.cgi?action=getDeviceType&session={session_id}"
            device_response = requests.get(info_url, timeout=5)
            
            if device_response.status_code != 200:
                self.logger.error(f"Error obteniendo información de dispositivo: {device_response.text}")
                return None
            
            # Consultar información de software
            version_url = f"{base_url}/magicBox.cgi?action=getSoftwareVersion&session={session_id}"
            version_response = requests.get(version_url, timeout=5)
            
            if version_response.status_code != 200:
                self.logger.error(f"Error obteniendo versión de software: {version_response.text}")
                return None
            
            # Parsear respuestas
            device_type = device_response.text.split('=')[1].strip() if 'deviceType' in device_response.text else 'Unknown'
            software_version = version_response.text.split('=')[1].strip() if 'version' in version_response.text else 'Unknown'
            
            return {
                'device_type': device_type,
                'software_version': software_version,
                'vendor': 'Dahua',
                'ip': ip
            }
            
        except Exception as e:
            self.logger.error(f"Error consultando información de dispositivo Dahua {ip}: {e}")
            return None
    
    def ptz_control(self, camera_config, command, speed=5, stop_after=None):
        """Control PTZ básico"""
        ip = camera_config['ip']
        channel = camera_config.get('channel', 1)
        
        # Asegurar que hay conexión
        if ip not in self.sessions:
            if not self.connect(camera_config):
                return False
        
        session = self.sessions[ip]
        base_url = session['base_url']
        session_id = session['id']
        
        # Mapeo de comandos a códigos PTZ de Dahua
        ptz_commands = {
            'up': 'Up',
            'down': 'Down',
            'left': 'Left',
            'right': 'Right',
            'upleft': 'LeftUp',
            'upright': 'RightUp',
            'downleft': 'LeftDown',
            'downright': 'RightDown',
            'stop': 'Stop',
            'zoom_in': 'ZoomTele',
            'zoom_out': 'ZoomWide',
            'home': 'Home'
        }
        
        if command.lower() not in ptz_commands:
            self.logger.error(f"Comando PTZ no soportado: {command}")
            return False
        
        ptz_command = ptz_commands[command.lower()]
        
        try:
            # Enviar comando PTZ
            ptz_url = f"{base_url}/ptz.cgi?action=start&channel={channel}&code={ptz_command}&arg1=0&arg2={speed}&arg3=0&session={session_id}"
            response = requests.get(ptz_url, timeout=5)
            
            if response.status_code != 200 or "Error" in response.text:
                self.logger.error(f"Error ejecutando comando PTZ: {response.text}")
                return False
            
            # Si se especificó, detener después de un tiempo
            if stop_after and command.lower() != 'stop':
                time.sleep(stop_after)
                stop_url = f"{base_url}/ptz.cgi?action=stop&channel={channel}&code={ptz_command}&arg1=0&arg2={speed}&arg3=0&session={session_id}"
                requests.get(stop_url, timeout=5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error controlando PTZ para cámara Dahua {ip}: {e}")
            return False
    
    def get_snapshot(self, camera_config, output_path=None):
        """Obtiene una captura instantánea de la cámara"""
        ip = camera_config['ip']
        channel = camera_config.get('channel', 1)
        
        # Construir URL para snapshot
        username = camera_config['username']
        password = camera_config['password']
        http_port = camera_config.get('http_port', 80)
        
        try:
            # URL directa para snapshot
            snapshot_url = f"http://{ip}:{http_port}/cgi-bin/snapshot.cgi?channel={channel}"
            
            # Realizar petición con autenticación
            response = requests.get(snapshot_url, auth=(username, password), timeout=5)
            
            if response.status_code != 200:
                self.logger.error(f"Error obteniendo snapshot: {response.status_code}")
                return None
            
            # Convertir respuesta a imagen
            image_array = np.frombuffer(response.content, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            # Guardar si se especificó una ruta
            if output_path and image is not None:
                cv2.imwrite(output_path, image)
                self.logger.info(f"Snapshot guardado en {output_path}")
            
            return image
            
        except Exception as e:
            self.logger.error(f"Error capturando snapshot de cámara Dahua {ip}: {e}")
            return None 