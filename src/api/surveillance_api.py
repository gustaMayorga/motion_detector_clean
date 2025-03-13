"""
vigIA - Sistema de Vigilancia Inteligente con IA
Versión PMV (Proyecto MOTION_DETECTOR)

© 2025 Gustavo Mayorga. Todos los derechos reservados.

Este código es propiedad exclusiva de Gustavo Mayorga y está protegido por leyes de 
propiedad intelectual. Ninguna parte de este software puede ser reproducida, distribuida, 
o utilizada para crear trabajos derivados sin autorización explícita por escrito.

Contacto legal: gustavo.mayorga.gm@gmail.com

AVISO: El uso no autorizado de este código o sus conceptos está estrictamente prohibido
y será perseguido en la máxima medida permitida por la ley.
"""

import time
import logging
import os
import json
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import cv2
import threading
import queue
import numpy as np
from datetime import datetime, timedelta
import uuid

# Importar componentes del sistema
from src.ai.object_detector import ObjectDetector
from src.ai.behavior_analyzer import BehaviorAnalyzer
from src.storage.video_indexer import VideoIndexer
from src.storage.storage_manager import StorageManager
from src.notifications.notification_manager import NotificationManager
from src.response.active_response import ActiveResponseManager
from src.training.adaptive_learning import AdaptiveLearningSystem

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SurveillanceAPI')

class SurveillanceAPI:
    """API REST para el sistema de vigilancia inteligente"""
    
    def __init__(self, config_path="configs/system.json"):
        """Inicializar API con configuración"""
        self.logger = logger
        self.config = self._load_config(config_path)
        
        # Inicializar Flask
        self.app = Flask(__name__)
        CORS(self.app)  # Habilitar CORS para frontend
        
        # Registrar rutas
        self._register_routes()
        
        # Estado del sistema
        self.cameras = {}
        self.detectors = {}
        self.analyzers = {}
        self.camera_streams = {}
        self.event_history = []
        self.active_alerts = []
        
        # Cola para eventos
        self.event_queue = queue.Queue(maxsize=100)
        
        # Inicializar componentes
        self._init_components()
        
        # Iniciar procesamiento en segundo plano
        self.running = True
        self.bg_thread = threading.Thread(target=self._background_processing)
        self.bg_thread.daemon = True
        self.bg_thread.start()
        
    def _load_config(self, config_path):
        """Cargar configuración desde archivo JSON"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            self.logger.error(f"Error al cargar configuración: {e}")
            # Usar configuración por defecto
            return {
                "api": {
                    "host": "0.0.0.0",
                    "port": 5000,
                    "debug": False
                },
                "storage": {
                    "recordings_path": "data/recordings",
                    "database_path": "data/surveillance.db",
                    "s3_enabled": False
                },
                "ai": {
                    "default_detector": "tensorflow",
                    "default_models_path": "models",
                    "batch_processing": True
                },
                "notifications": {
                    "email_enabled": False,
                    "sms_enabled": False,
                    "push_enabled": False
                },
                "cameras": {}
            }
            
    def _init_components(self):
        """Inicializar componentes del sistema"""
        try:
            # Inicializar gestor de almacenamiento
            storage_config = self.config.get("storage", {})
            self.storage_manager = StorageManager(storage_config)
            
            # Inicializar indexador de videos
            self.video_indexer = VideoIndexer(
                db_path=storage_config.get("database_path", "data/surveillance.db")
            )
            self.storage_manager.video_indexer = self.video_indexer
            
            # Inicializar gestor de notificaciones
            notification_config = self.config.get("notifications", {})
            self.notification_manager = NotificationManager(notification_config)
            
            # Inicializar gestor de respuestas activas
            response_config = self.config.get("responses", {})
            self.response_manager = ActiveResponseManager(response_config)
            
            # Inicializar cámaras configuradas
            self._init_cameras()
            
            # Inicializar sistema de aprendizaje adaptativo
            learning_config = self.config.get("learning", {})
            if not learning_config.get("client_id"):
                learning_config["client_id"] = "client_" + str(uuid.uuid4())[:8]
            self.learning_system = AdaptiveLearningSystem(learning_config)
            
            self.logger.info("Componentes del sistema inicializados correctamente")
            
        except Exception as e:
            self.logger.error(f"Error al inicializar componentes: {e}")
            raise
            
    def _init_cameras(self):
        """Inicializar cámaras configuradas"""
        cameras_config = self.config.get("cameras", {})
        
        for camera_id, camera_config in cameras_config.items():
            try:
                # Registrar cámara
                self.cameras[camera_id] = {
                    "id": camera_id,
                    "name": camera_config.get("name", f"Camera {camera_id}"),
                    "url": camera_config.get("url", ""),
                    "type": camera_config.get("type", "rtsp"),
                    "location": camera_config.get("location", ""),
                    "status": "offline",
                    "last_error": None,
                    "frame_count": 0,
                    "resolution": camera_config.get("resolution", "640x480"),
                    "fps": camera_config.get("fps", 10),
                    "recording": camera_config.get("auto_record", False),
                    "alerts_enabled": camera_config.get("alerts_enabled", True)
                }
                
                # Inicializar detector para esta cámara
                detector_config = camera_config.get("detector", {})
                if not detector_config:
                    # Usar configuración por defecto
                    ai_config = self.config.get("ai", {})
                    detector_config = {
                        "model_type": ai_config.get("default_detector", "tensorflow"),
                        "model_path": os.path.join(
                            ai_config.get("default_models_path", "models"),
                            "ssd_mobilenet_v2_coco"
                        ),
                        "confidence_threshold": 0.5,
                        "classes_of_interest": ["person", "car", "truck"]
                    }
                    
                self.detectors[camera_id] = ObjectDetector(detector_config)
                
                # Inicializar analizador de comportamiento
                analyzer_config = camera_config.get("analyzer", {})
                self.analyzers[camera_id] = BehaviorAnalyzer(analyzer_config)
                
                self.logger.info(f"Cámara {camera_id} ({self.cameras[camera_id]['name']}) inicializada")
                
            except Exception as e:
                self.logger.error(f"Error al inicializar cámara {camera_id}: {e}")
                
    def _register_routes(self):
        """Registrar rutas de la API REST"""
        
        # Rutas de estado del sistema
        self.app.route('/api/status')(self.get_system_status)
        
        # Rutas de cámaras
        self.app.route('/api/cameras')(self.get_cameras)
        self.app.route('/api/cameras/<camera_id>')(self.get_camera)
        self.app.route('/api/cameras/<camera_id>', methods=['PUT'])(self.update_camera)
        self.app.route('/api/cameras/<camera_id>/stream')(self.get_camera_stream)
        self.app.route('/api/cameras/<camera_id>/snapshot')(self.get_camera_snapshot)
        self.app.route('/api/cameras/<camera_id>/start_recording', methods=['POST'])(self.start_recording)
        self.app.route('/api/cameras/<camera_id>/stop_recording', methods=['POST'])(self.stop_recording)
        
        # Rutas de alertas y eventos
        self.app.route('/api/alerts')(self.get_alerts)
        self.app.route('/api/alerts/<alert_id>')(self.get_alert)
        self.app.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])(self.acknowledge_alert)
        self.app.route('/api/events')(self.get_events)
        
        # Rutas de grabaciones
        self.app.route('/api/recordings')(self.get_recordings)
        self.app.route('/api/recordings/<recording_id>')(self.get_recording)
        self.app.route('/api/recordings/<recording_id>/download')(self.download_recording)
        self.app.route('/api/recordings/<recording_id>', methods=['DELETE'])(self.delete_recording)
        
        # Rutas de configuración
        self.app.route('/api/config')(self.get_config)
        self.app.route('/api/config', methods=['PUT'])(self.update_config)
        self.app.route('/api/config/<section>')(self.get_config_section)
        self.app.route('/api/config/<section>', methods=['PUT'])(self.update_config_section)
        
        # Rutas de analítica
        self.app.route('/api/stats')(self.get_statistics)
        self.app.route('/api/stats/<stat_type>')(self.get_specific_statistics)
        
        # Ruta de gestión de zonas
        self.app.route('/api/cameras/<camera_id>/zones')(self.get_zones)
        self.app.route('/api/cameras/<camera_id>/zones', methods=['POST'])(self.create_zone)
        self.app.route('/api/cameras/<camera_id>/zones/<zone_id>', methods=['PUT'])(self.update_zone)
        self.app.route('/api/cameras/<camera_id>/zones/<zone_id>', methods=['DELETE'])(self.delete_zone)
        
        # Rutas para sistema de aprendizaje adaptativo
        self.app.route('/api/learning/status')(self.get_learning_status)
        self.app.route('/api/learning/train', methods=['POST'])(self.train_models)
        self.app.route('/api/learning/parameters')(self.get_optimized_parameters)
        self.app.route('/api/learning/simulation', methods=['POST'])(self.run_simulation)
        self.app.route('/api/learning/feedback/<event_id>', methods=['POST'])(self.register_feedback)
        
        # Rutas para reconocimiento facial
        self.app.route('/api/faces')(self.get_registered_faces)
        self.app.route('/api/faces/<person_id>')(self.get_person_info)
        self.app.route('/api/faces/<person_id>', methods=['DELETE'])(self.delete_person)
        self.app.route('/api/faces/<person_id>', methods=['PUT'])(self.update_person_info)
        self.app.route('/api/faces/register', methods=['POST'])(self.register_face)
        self.app.route('/api/cameras/<camera_id>/detect_faces')(self.detect_faces_in_camera)
        self.app.route('/api/faces/watchlist', methods=['GET'])(self.get_watchlist)
        self.app.route('/api/faces/<person_id>/watchlist', methods=['POST'])(self.add_to_watchlist)
        self.app.route('/api/faces/<person_id>/watchlist', methods=['DELETE'])(self.remove_from_watchlist)
        
    def _background_processing(self):
        """Procesamiento en segundo plano para detección y análisis"""
        self.logger.info("Iniciando hilo de procesamiento en segundo plano")
        
        while self.running:
            # Procesar cámaras activas
            for camera_id, camera_info in self.cameras.items():
                try:
                    # Solo procesar cámaras activas
                    if camera_info.get("status") != "online":
                        continue
                    
                    # Obtener stream de la cámara
                    stream = self.camera_streams.get(camera_id)
                    if not stream or not stream.get("cap"):
                        continue
                    
                    cap = stream.get("cap")
                    ret, frame = cap.read()
                    
                    if not ret or frame is None:
                        # Error al leer frame
                        self.logger.warning(f"Error al leer frame de la cámara {camera_id}")
                        continue
                    
                    # Incrementar contador de frames
                    camera_info["frame_count"] += 1
                    
                    # Decidir si procesar este frame (reducir carga)
                    frame_count = camera_info["frame_count"]
                    if frame_count % 5 != 0:  # Procesar cada 5 frames
                        continue
                    
                    # Detectar objetos
                    detector = self.detectors.get(camera_id)
                    if detector:
                        detections = detector.detect(frame)
                        
                        # Analizar comportamiento
                        analyzer = self.analyzers.get(camera_id)
                        if analyzer and detections:
                            events, annotated_frame = analyzer.process_frame(frame, detections)
                            
                            # Procesar eventos detectados
                            if events:
                                for event in events:
                                    self._process_event(camera_id, event, frame)
                    
                    # Grabar si está en modo grabación
                    if camera_info.get("recording"):
                        self._record_frame(camera_id, frame)
                        
                except Exception as e:
                    self.logger.error(f"Error en procesamiento de cámara {camera_id}: {e}")
            
            # Pequeña pausa para evitar consumo excesivo de CPU
            time.sleep(0.01)
    
    def _process_event(self, camera_id, event, frame):
        """Procesar un evento detectado"""
        # Generar ID único para el evento
        event_id = str(uuid.uuid4())
        
        # Enriquecer evento con metadatos
        event_data = {
            "id": event_id,
            "camera_id": camera_id,
            "camera_name": self.cameras[camera_id]["name"],
            "timestamp": datetime.now().isoformat(),
            "type": event["type"],
            "confidence": event.get("confidence", 1.0),
            "details": event,
            "status": "new"
        }
        
        # Guardar snapshot del evento
        snapshot_path = self._save_event_snapshot(camera_id, event_id, frame, event)
        if snapshot_path:
            event_data["snapshot"] = snapshot_path
        
        # Agregar a historial
        self.event_history.append(event_data)
        
        # Si es una alerta activa
        if event["type"] in ["intrusion", "tailgating", "abandoned_object"]:
            self.active_alerts.append(event_data)
            
            # Enviar notificación
            self._send_alert_notification(event_data)
            
        # Si es una alerta activa que requiere respuesta inmediata
        if event["type"] in ["intrusion", "tailgating"] and \
           self.config.get("responses", {}).get("auto_respond", False):
            # Enviar advertencia por altavoz
            self.response_manager.queue_audio_warning(
                message=None,  # Usar mensaje predeterminado
                event_data=event_data,
                device=self.cameras[camera_id].get("speaker_device", "default")
            )
        
        # Poner en cola para WebSocket
        try:
            self.event_queue.put_nowait(event_data)
        except queue.Full:
            # Si la cola está llena, eliminar el evento más antiguo
            try:
                self.event_queue.get_nowait()
                self.event_queue.put_nowait(event_data)
            except:
                pass
        
        # Registrar evento para aprendizaje
        self.learning_system.register_event(event_data)
    
    def _save_event_snapshot(self, camera_id, event_id, frame, event):
        """Guardar imagen del evento"""
        try:
            # Crear directorio si no existe
            snapshots_dir = os.path.join(
                self.config["storage"].get("recordings_path", "data/recordings"),
                "snapshots"
            )
            os.makedirs(snapshots_dir, exist_ok=True)
            
            # Construir ruta del archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{camera_id}_{event['type']}_{timestamp}_{event_id[:8]}.jpg"
            filepath = os.path.join(snapshots_dir, filename)
            
            # Guardar imagen
            cv2.imwrite(filepath, frame)
            
            return filepath
        except Exception as e:
            self.logger.error(f"Error al guardar snapshot de evento: {e}")
            return None
    
    def _send_alert_notification(self, alert_data):
        """Enviar notificación de alerta"""
        try:
            # Preparar mensaje
            camera_name = alert_data["camera_name"]
            alert_type = alert_data["type"]
            timestamp = datetime.fromisoformat(alert_data["timestamp"]).strftime("%H:%M:%S")
            
            subject = f"Alerta de seguridad: {alert_type.upper()} detectado"
            message = (
                f"Se ha detectado un evento de {alert_type} en la cámara {camera_name} "
                f"a las {timestamp}.\n\n"
                f"ID de alerta: {alert_data['id']}\n"
                f"Confianza: {alert_data['confidence']:.2f}"
            )
            
            # Añadir detalles específicos según tipo
            if alert_type == "intrusion":
                zone = alert_data["details"].get("zone", "desconocida")
                message += f"\nZona de intrusión: {zone}"
            elif alert_type == "tailgating":
                message += "\nPosible acceso no autorizado por seguimiento."
            
            # Enviar notificación
            self.notification_manager.send_alert(
                subject=subject,
                message=message,
                priority="high",
                attachment=alert_data.get("snapshot"),
                metadata=alert_data
            )
            
        except Exception as e:
            self.logger.error(f"Error al enviar notificación: {e}")
    
    def _record_frame(self, camera_id, frame):
        """Guardar frame para grabación"""
        try:
            camera_stream = self.camera_streams.get(camera_id, {})
            recorder = camera_stream.get("recorder")
            
            if recorder and hasattr(recorder, "write"):
                recorder.write(frame)
            
        except Exception as e:
            self.logger.error(f"Error al grabar frame: {e}")
    
    # Métodos de la API REST
    
    def get_system_status(self):
        """Obtener estado general del sistema"""
        try:
            # Recopilar estadísticas
            camera_count = len(self.cameras)
            online_cameras = sum(1 for c in self.cameras.values() if c.get("status") == "online")
            active_alerts = len(self.active_alerts)
            
            disk_usage = self.storage_manager.get_storage_usage()
            
            # Estado general
            status = {
                "status": "operational" if online_cameras > 0 else "degraded",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",  # Versión del sistema
                "statistics": {
                    "cameras": {
                        "total": camera_count,
                        "online": online_cameras,
                        "offline": camera_count - online_cameras
                    },
                    "alerts": {
                        "active": active_alerts,
                        "total": len(self.event_history)
                    },
                    "storage": disk_usage
                }
            }
            
            return jsonify(status)
        except Exception as e:
            self.logger.error(f"Error al obtener estado del sistema: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_cameras(self):
        """Obtener lista de cámaras"""
        try:
            # Filtrar información sensible como URLs internas
            cameras_info = []
            for camera_id, camera in self.cameras.items():
                cameras_info.append({
                    "id": camera_id,
                    "name": camera.get("name", ""),
                    "location": camera.get("location", ""),
                    "status": camera.get("status", "offline"),
                    "recording": camera.get("recording", False),
                    "alerts_enabled": camera.get("alerts_enabled", True),
                    "resolution": camera.get("resolution", ""),
                    "frame_count": camera.get("frame_count", 0)
                })
            
            return jsonify(cameras_info)
        except Exception as e:
            self.logger.error(f"Error al obtener lista de cámaras: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_camera(self, camera_id):
        """Obtener información de una cámara específica"""
        try:
            if camera_id not in self.cameras:
                return jsonify({"error": "Cámara no encontrada"}), 404
            
            camera = self.cameras[camera_id]
            
            # Incluir estadísticas específicas
            camera_stats = {
                "id": camera_id,
                "name": camera.get("name", ""),
                "location": camera.get("location", ""),
                "status": camera.get("status", "offline"),
                "type": camera.get("type", "rtsp"),
                "resolution": camera.get("resolution", ""),
                "fps": camera.get("fps", 0),
                "recording": camera.get("recording", False),
                "alerts_enabled": camera.get("alerts_enabled", True),
                "frame_count": camera.get("frame_count", 0),
                "uptime": camera.get("uptime", 0),
                "last_error": camera.get("last_error")
            }
            
            # Si hay analizador, incluir zona y conteos
            analyzer = self.analyzers.get(camera_id)
            if analyzer:
                camera_stats["zones"] = list(analyzer.config.get("zones", {}).keys())
                camera_stats["object_counts"] = {
                    "person": analyzer.get_object_count("person"),
                    "vehicle": analyzer.get_object_count(["car", "truck", "bus"]),
                    "total": analyzer.get_object_count()
                }
                camera_stats["zone_counts"] = analyzer.get_zone_counts()
            
            return jsonify(camera_stats)
        except Exception as e:
            self.logger.error(f"Error al obtener información de cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def update_camera(self, camera_id):
        """Actualizar configuración de una cámara"""
        try:
            if camera_id not in self.cameras:
                return jsonify({"error": "Cámara no encontrada"}), 404
            
            # Obtener datos del request
            data = request.json
            if not data:
                return jsonify({"error": "Datos no válidos"}), 400
            
            # Campos permitidos para actualizar
            allowed_fields = [
                "name", "location", "alerts_enabled", "fps", 
                "resolution", "type", "url"
            ]
            
            # Actualizar campos permitidos
            for field in allowed_fields:
                if field in data:
                    self.cameras[camera_id][field] = data[field]
            
            # Si se actualiza la URL, reiniciar conexión
            if "url" in data:
                self._reconnect_camera(camera_id)
                
            # Guardar configuración actualizada
            self._save_config()
            
            return jsonify({"status": "success", "message": "Cámara actualizada correctamente"})
        
        except Exception as e:
            self.logger.error(f"Error al actualizar cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _reconnect_camera(self, camera_id):
        """Reconectar a una cámara (cerrar y abrir stream)"""
        try:
            # Cerrar stream si existe
            if camera_id in self.camera_streams:
                stream_info = self.camera_streams[camera_id]
                if "cap" in stream_info and stream_info["cap"]:
                    stream_info["cap"].release()
                
                if "recorder" in stream_info and stream_info["recorder"]:
                    stream_info["recorder"].release()
                    
                del self.camera_streams[camera_id]
            
            # Marcar como offline
            self.cameras[camera_id]["status"] = "connecting"
            
            # Iniciar nuevo stream
            self._connect_camera(camera_id)
            
        except Exception as e:
            self.logger.error(f"Error al reconectar cámara {camera_id}: {e}")
            self.cameras[camera_id]["status"] = "error"
            self.cameras[camera_id]["last_error"] = str(e)
    
    def _connect_camera(self, camera_id):
        """Conectar a una cámara y abrir stream"""
        try:
            camera = self.cameras[camera_id]
            url = camera.get("url", "")
            
            if not url:
                self.logger.error(f"URL no especificada para cámara {camera_id}")
                camera["status"] = "error"
                camera["last_error"] = "URL no especificada"
                return False
                
            # Crear thread para conexión (evitar bloqueo)
            thread = threading.Thread(
                target=self._camera_connection_thread,
                args=(camera_id, url)
            )
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error al conectar con cámara {camera_id}: {e}")
            self.cameras[camera_id]["status"] = "error"
            self.cameras[camera_id]["last_error"] = str(e)
            return False
    
    def _camera_connection_thread(self, camera_id, url):
        """Thread para conectar a cámara sin bloquear"""
        try:
            # Determinar fuente (URL o número de cámara)
            if url.isdigit():
                # Cámara local
                source = int(url)
            else:
                # URL de cámara
                source = url
                
            # Intentar abrir la cámara
            cap = cv2.VideoCapture(source)
            
            if not cap.isOpened():
                raise Exception("No se pudo abrir la cámara")
                
            # Configurar parámetros
            camera = self.cameras[camera_id]
            
            # Establecer resolución si está especificada
            resolution = camera.get("resolution", "")
            if resolution:
                try:
                    width, height = map(int, resolution.split("x"))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                except:
                    self.logger.warning(f"Formato de resolución inválido: {resolution}")
                    
            # Establecer FPS si está especificado
            fps = camera.get("fps", 0)
            if fps > 0:
                cap.set(cv2.CAP_PROP_FPS, fps)
                
            # Leer frame para verificar conexión
            ret, frame = cap.read()
            if not ret:
                raise Exception("No se pudo leer frame de la cámara")
                
            # Guardar resolución real
            real_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            real_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            camera["resolution"] = f"{real_width}x{real_height}"
            
            # Guardar FPS real
            real_fps = cap.get(cv2.CAP_PROP_FPS)
            camera["fps"] = real_fps
                
            # Guardar stream
            self.camera_streams[camera_id] = {
                "cap": cap,
                "recorder": None,
                "last_frame": frame,
                "last_updated": time.time()
            }
            
            # Actualizar estado
            camera["status"] = "online"
            camera["last_error"] = None
            camera["connected_at"] = time.time()
            
            self.logger.info(f"Cámara {camera_id} conectada correctamente ({real_width}x{real_height} @ {real_fps}fps)")
            
            # Iniciar grabación si está configurada
            if camera.get("auto_record", False):
                self.start_recording(camera_id)
                
        except Exception as e:
            self.logger.error(f"Error al conectar con cámara {camera_id}: {e}")
            self.cameras[camera_id]["status"] = "error"
            self.cameras[camera_id]["last_error"] = str(e)
    
    def get_camera_stream(self, camera_id):
        """Obtener stream MJPEG de una cámara"""
        if camera_id not in self.cameras:
            return jsonify({"error": "Cámara no encontrada"}), 404
            
        if self.cameras[camera_id].get("status") != "online":
            return jsonify({"error": "Cámara no disponible"}), 503
            
        # Stream MJPEG
        return Response(
            self._generate_camera_stream(camera_id),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
        
    def _generate_camera_stream(self, camera_id):
        """Generador para stream MJPEG"""
        try:
            while True:
                # Obtener stream
                stream = self.camera_streams.get(camera_id)
                if not stream:
                    yield (b'--frame\r\n'
                          b'Content-Type: text/plain\r\n\r\n'
                          b'Camera Offline\r\n\r\n')
                    time.sleep(1)
                    continue
                
                # Obtener último frame o leer nuevo
                if time.time() - stream.get("last_updated", 0) > 0.1:
                    # Leer nuevo frame
                    cap = stream.get("cap")
                    if not cap:
                        yield (b'--frame\r\n'
                              b'Content-Type: text/plain\r\n\r\n'
                              b'Camera Offline\r\n\r\n')
                        time.sleep(1)
                        continue
                        
                    ret, frame = cap.read()
                    if not ret:
                        yield (b'--frame\r\n'
                              b'Content-Type: text/plain\r\n\r\n'
                              b'Error reading frame\r\n\r\n')
                        time.sleep(1)
                        continue
                        
                    # Actualizar último frame
                    stream["last_frame"] = frame
                    stream["last_updated"] = time.time()
                else:
                    # Usar último frame
                    frame = stream.get("last_frame")
                    if frame is None:
                        yield (b'--frame\r\n'
                              b'Content-Type: text/plain\r\n\r\n'
                              b'No frame available\r\n\r\n')
                        time.sleep(1)
                        continue
                
                # Redimensionar para stream (opcional)
                # frame = cv2.resize(frame, (640, 480))
                
                # Convertir a JPG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                jpg_bytes = buffer.tobytes()
                
                # Enviar frame
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + jpg_bytes + b'\r\n')
                
                # Pausa para controlar FPS del stream
                time.sleep(0.03)  # ~30fps
                
        except GeneratorExit:
            # Cliente cerró la conexión
            pass
        except Exception as e:
            self.logger.error(f"Error en stream de cámara {camera_id}: {e}")
            yield (b'--frame\r\n'
                  b'Content-Type: text/plain\r\n\r\n'
                  f'Error: {str(e)}\r\n\r\n'.encode())
    
    def get_camera_snapshot(self, camera_id):
        """Obtener snapshot/imagen actual de una cámara"""
        if camera_id not in self.cameras:
            return jsonify({"error": "Cámara no encontrada"}), 404
            
        if self.cameras[camera_id].get("status") != "online":
            return jsonify({"error": "Cámara no disponible"}), 503
            
        try:
            # Obtener stream
            stream = self.camera_streams.get(camera_id)
            if not stream:
                return jsonify({"error": "Stream no disponible"}), 503
                
            # Obtener último frame o leer nuevo
            if time.time() - stream.get("last_updated", 0) > 0.5:
                # Leer nuevo frame
                cap = stream.get("cap")
                if not cap:
                    return jsonify({"error": "Cámara no disponible"}), 503
                    
                ret, frame = cap.read()
                if not ret:
                    return jsonify({"error": "Error al leer frame"}), 500
                    
                # Actualizar último frame
                stream["last_frame"] = frame
                stream["last_updated"] = time.time()
            else:
                # Usar último frame
                frame = stream.get("last_frame")
                if frame is None:
                    return jsonify({"error": "Frame no disponible"}), 500
            
            # Convertir a JPG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            jpg_bytes = buffer.tobytes()
            
            # Devolver imagen
            return Response(jpg_bytes, mimetype='image/jpeg')
            
        except Exception as e:
            self.logger.error(f"Error al obtener snapshot de cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def start_recording(self, camera_id):
        """Iniciar grabación de una cámara"""
        if camera_id not in self.cameras:
            return jsonify({"error": "Cámara no encontrada"}), 404
            
        if self.cameras[camera_id].get("status") != "online":
            return jsonify({"error": "Cámara no disponible"}), 503
            
        try:
            # Verificar si ya está grabando
            if self.cameras[camera_id].get("recording", False):
                return jsonify({"status": "success", "message": "La cámara ya está grabando"})
                
            # Obtener stream
            stream = self.camera_streams.get(camera_id)
            if not stream or not stream.get("cap"):
                return jsonify({"error": "Stream no disponible"}), 503
                
            # Crear directorio para grabaciones
            recordings_dir = os.path.join(
                self.config["storage"].get("recordings_path", "data/recordings"),
                camera_id
            )
            os.makedirs(recordings_dir, exist_ok=True)
            
            # Nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{camera_id}_{timestamp}.mp4"
            filepath = os.path.join(recordings_dir, filename)
            
            # Obtener fps y resolución
            cap = stream.get("cap")
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            if fps == 0:
                fps = 30  # Valor por defecto
                
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Crear objeto de grabación
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            recorder = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            if not recorder.isOpened():
                return jsonify({"error": "No se pudo crear grabación"}), 500
                
            # Guardar referencia
            stream["recorder"] = recorder
            stream["recording_start"] = time.time()
            stream["recording_file"] = filepath
            
            # Actualizar estado
            self.cameras[camera_id]["recording"] = True
            self.cameras[camera_id]["current_recording"] = {
                "id": timestamp,
                "filename": filename,
                "filepath": filepath,
                "start_time": datetime.now().isoformat()
            }
            
            # Registrar en indexador
            recording_id = self.video_indexer.register_recording(
                camera_id=camera_id,
                filepath=filepath,
                timestamp=datetime.now(),
                duration=0,  # Se actualizará al finalizar
                metadata={
                    "resolution": f"{width}x{height}",
                    "fps": fps,
                    "size": 0  # Se actualizará al finalizar
                }
            )
            
            stream["recording_id"] = recording_id
            
            self.logger.info(f"Iniciada grabación de cámara {camera_id}: {filepath}")
            
            return jsonify({
                "status": "success", 
                "message": "Grabación iniciada",
                "recording_id": timestamp,
                "file": filename
            })
            
        except Exception as e:
            self.logger.error(f"Error al iniciar grabación de cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def stop_recording(self, camera_id):
        """Detener grabación de una cámara"""
        if camera_id not in self.cameras:
            return jsonify({"error": "Cámara no encontrada"}), 404
            
        try:
            # Verificar si está grabando
            if not self.cameras[camera_id].get("recording", False):
                return jsonify({"status": "success", "message": "La cámara no está grabando"})
                
            # Obtener stream
            stream = self.camera_streams.get(camera_id)
            if not stream:
                return jsonify({"error": "Stream no disponible"}), 503
                
            # Obtener grabadora
            recorder = stream.get("recorder")
            if recorder:
                # Liberar grabadora
                recorder.release()
                
                # Actualizar metadatos en indexador
                recording_id = stream.get("recording_id")
                if recording_id:
                    filepath = stream.get("recording_file", "")
                    if os.path.exists(filepath):
                        # Calcular duración y tamaño
                        duration = time.time() - stream.get("recording_start", time.time())
                        size = os.path.getsize(filepath)
                        
                        # Actualizar en indexador
                        self.video_indexer.update_recording(
                            recording_id=recording_id,
                            duration=duration,
                            metadata={
                                "size": size
                            }
                        )
                
            # Limpiar referencias
            stream["recorder"] = None
            stream["recording_start"] = None
            stream["recording_file"] = None
            stream["recording_id"] = None
            
            # Actualizar estado
            current_recording = self.cameras[camera_id].get("current_recording", {})
            self.cameras[camera_id]["recording"] = False
            self.cameras[camera_id]["current_recording"] = None
            
            self.logger.info(f"Detenida grabación de cámara {camera_id}")
            
            return jsonify({
                "status": "success", 
                "message": "Grabación detenida",
                "recording": current_recording
            })
            
        except Exception as e:
            self.logger.error(f"Error al detener grabación de cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_alerts(self):
        """Obtener lista de alertas activas"""
        try:
            # Obtener parámetros de filtrado
            status = request.args.get('status', 'active')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
            
            # Filtrar alertas según estado
            if status == 'active':
                alerts = self.active_alerts
            elif status == 'all':
                alerts = self.event_history
            else:
                alerts = [a for a in self.event_history if a.get("status") == status]
                
            # Ordenar por timestamp (más reciente primero)
            sorted_alerts = sorted(
                alerts, 
                key=lambda a: a.get("timestamp", ""), 
                reverse=True
            )
            
            # Aplicar paginación
            paginated = sorted_alerts[offset:offset+limit]
            
            # Formato para respuesta
            result = {
                "total": len(sorted_alerts),
                "limit": limit,
                "offset": offset,
                "alerts": paginated
            }
            
            return jsonify(result)
            
        except Exception as e:
            self.logger.error(f"Error al obtener alertas: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_alert(self, alert_id):
        """Obtener detalles de una alerta específica"""
        try:
            # Buscar alerta por ID
            for alert in self.event_history:
                if alert.get("id") == alert_id:
                    return jsonify(alert)
                    
            return jsonify({"error": "Alerta no encontrada"}), 404
            
        except Exception as e:
            self.logger.error(f"Error al obtener alerta {alert_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def acknowledge_alert(self, alert_id):
        """Marcar una alerta como atendida"""
        try:
            # Buscar alerta en activas
            for i, alert in enumerate(self.active_alerts):
                if alert.get("id") == alert_id:
                    # Marcar como atendida
                    self.active_alerts[i]["status"] = "acknowledged"
                    
                    # Actualizar también en historial
                    for event in self.event_history:
                        if event.get("id") == alert_id:
                            event["status"] = "acknowledged"
                            event["acknowledged_at"] = datetime.now().isoformat()
                    
                    return jsonify({
                        "status": "success",
                        "message": "Alerta marcada como atendida"
                    })
            
            return jsonify({"error": "Alerta no encontrada"}), 404
            
        except Exception as e:
            self.logger.error(f"Error al marcar alerta {alert_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_events(self):
        """Obtener historial de eventos"""
        try:
            # Obtener parámetros de filtrado
            event_type = request.args.get('type')
            camera_id = request.args.get('camera')
            from_date = request.args.get('from')
            to_date = request.args.get('to')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
            
            # Lista base de eventos
            events = self.event_history.copy()
            
            # Aplicar filtros
            if event_type:
                events = [e for e in events if e.get("type") == event_type]
                
            if camera_id:
                events = [e for e in events if e.get("camera_id") == camera_id]
                
            if from_date:
                try:
                    from_dt = datetime.fromisoformat(from_date)
                    events = [e for e in events if datetime.fromisoformat(e.get("timestamp", "")) >= from_dt]
                except:
                    pass
                    
            if to_date:
                try:
                    to_dt = datetime.fromisoformat(to_date)
                    events = [e for e in events if datetime.fromisoformat(e.get("timestamp", "")) <= to_dt]
                except:
                    pass
            
            # Ordenar por timestamp (más reciente primero)
            sorted_events = sorted(
                events, 
                key=lambda e: e.get("timestamp", ""), 
                reverse=True
            )
            
            # Aplicar paginación
            paginated = sorted_events[offset:offset+limit]
            
            # Formato para respuesta
            result = {
                "total": len(sorted_events),
                "limit": limit,
                "offset": offset,
                "events": paginated
            }
            
            return jsonify(result)
            
        except Exception as e:
            self.logger.error(f"Error al obtener eventos: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_recordings(self):
        """Obtener lista de grabaciones"""
        try:
            # Obtener parámetros de filtrado
            camera_id = request.args.get('camera')
            from_date = request.args.get('from')
            to_date = request.args.get('to')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))
            
            # Consultar indexador
            recordings = self.video_indexer.get_recordings(
                camera_id=camera_id,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
                offset=offset
            )
            
            return jsonify(recordings)
            
        except Exception as e:
            self.logger.error(f"Error al obtener grabaciones: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_recording(self, recording_id):
        """Obtener detalles de una grabación específica"""
        try:
            # Consultar indexador
            recording = self.video_indexer.get_recording(recording_id)
            
            if not recording:
                return jsonify({"error": "Grabación no encontrada"}), 404
                
            return jsonify(recording)
            
        except Exception as e:
            self.logger.error(f"Error al obtener grabación {recording_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def download_recording(self, recording_id):
        """Descargar archivo de grabación"""
        try:
            # Consultar indexador
            recording = self.video_indexer.get_recording(recording_id)
            
            if not recording:
                return jsonify({"error": "Grabación no encontrada"}), 404
                
            filepath = recording.get("filepath")
            
            if not filepath or not os.path.exists(filepath):
                return jsonify({"error": "Archivo no encontrado"}), 404
                
            return send_file(
                filepath,
                as_attachment=True,
                attachment_filename=os.path.basename(filepath),
                mimetype='video/mp4'
            )
            
        except Exception as e:
            self.logger.error(f"Error al descargar grabación {recording_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def delete_recording(self, recording_id):
        """Eliminar una grabación"""
        try:
            # Consultar indexador
            recording = self.video_indexer.get_recording(recording_id)
            
            if not recording:
                return jsonify({"error": "Grabación no encontrada"}), 404
                
            filepath = recording.get("filepath")
            
            # Intentar eliminar archivo
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                
            # Eliminar del indexador
            self.video_indexer.delete_recording(recording_id)
            
            return jsonify({
                "status": "success",
                "message": "Grabación eliminada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al eliminar grabación {recording_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_config(self):
        """Obtener configuración completa del sistema"""
        try:
            # Excluir información sensible
            filtered_config = self.config.copy()
            
            # Filtrar URLs y credenciales de cámaras
            if "cameras" in filtered_config:
                for camera_id, camera in filtered_config["cameras"].items():
                    if "password" in camera:
                        camera["password"] = "********"
            
            # Filtrar credenciales de almacenamiento
            if "storage" in filtered_config and "s3" in filtered_config["storage"]:
                s3_config = filtered_config["storage"]["s3"]
                if "secret_key" in s3_config:
                    s3_config["secret_key"] = "********"
            
            # Filtrar credenciales de notificaciones
            if "notifications" in filtered_config:
                notif_config = filtered_config["notifications"]
                for provider in ["email", "sms", "push"]:
                    if provider in notif_config and "password" in notif_config[provider]:
                        notif_config[provider]["password"] = "********"
            
            return jsonify(filtered_config)
            
        except Exception as e:
            self.logger.error(f"Error al obtener configuración: {e}")
            return jsonify({"error": str(e)}), 500
    
    def update_config(self):
        """Actualizar configuración completa del sistema"""
        try:
            # Verificar permisos (aquí se podría implementar autenticación)
            
            # Obtener datos
            data = request.json
            if not data:
                return jsonify({"error": "Datos no válidos"}), 400
                
            # Hacer backup de configuración actual
            backup_config = self.config.copy()
            
            # Actualizar configuración
            self.config.update(data)
            
            # Guardar cambios
            if not self._save_config():
                # Restaurar backup si hay error
                self.config = backup_config
                return jsonify({"error": "Error al guardar configuración"}), 500
                
            # Reiniciar componentes afectados
            self._reinitialize_components()
            
            return jsonify({
                "status": "success",
                "message": "Configuración actualizada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al actualizar configuración: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_config_section(self, section):
        """Obtener una sección específica de la configuración"""
        try:
            if section not in self.config:
                return jsonify({"error": f"Sección {section} no encontrada"}), 404
                
            # Filtrar información sensible
            filtered_section = self.config[section].copy()
            
            # Filtrar según sección
            if section == "cameras":
                for camera_id, camera in filtered_section.items():
                    if "password" in camera:
                        camera["password"] = "********"
            elif section == "storage" and "s3" in filtered_section:
                if "secret_key" in filtered_section["s3"]:
                    filtered_section["s3"]["secret_key"] = "********"
            elif section == "notifications":
                for provider in ["email", "sms", "push"]:
                    if provider in filtered_section and "password" in filtered_section[provider]:
                        filtered_section[provider]["password"] = "********"
            
            return jsonify(filtered_section)
            
        except Exception as e:
            self.logger.error(f"Error al obtener sección {section}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def update_config_section(self, section):
        """Actualizar una sección específica de la configuración"""
        try:
            if section not in self.config:
                return jsonify({"error": f"Sección {section} no encontrada"}), 404
                
            # Obtener datos
            data = request.json
            if not data:
                return jsonify({"error": "Datos no válidos"}), 400
                
            # Hacer backup de configuración actual
            backup_section = self.config[section].copy()
            
            # Actualizar sección
            self.config[section] = data
            
            # Guardar cambios
            if not self._save_config():
                # Restaurar backup si hay error
                self.config[section] = backup_section
                return jsonify({"error": "Error al guardar configuración"}), 500
                
            # Reiniciar componentes según sección
            if section == "cameras":
                self._init_cameras()
            elif section == "storage":
                self._init_components()
            elif section == "notifications":
                self.notification_manager = NotificationManager(data)
            
            return jsonify({
                "status": "success",
                "message": f"Sección {section} actualizada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al actualizar sección {section}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def _save_config(self):
        """Guardar configuración a archivo"""
        try:
            # Asegurarse de que self.config_path está definido
            config_path = getattr(self, 'config_path', "configs/system.json")
            
            # Crear directorio si no existe
            config_dir = os.path.dirname(config_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # Guardar configuración
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.logger.info(f"Configuración guardada en {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error al guardar configuración: {e}")
            return False
    
    def _reinitialize_components(self):
        """Reinicializar componentes del sistema"""
        try:
            # Reiniciar componentes
            self._init_components()
            self.logger.info("Componentes reinicializados correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"Error al reinicializar componentes: {e}")
            return False
    
    def get_statistics(self):
        """Obtener estadísticas generales del sistema"""
        try:
            # Asegurarse de que start_time está definido
            start_time = getattr(self, 'start_time', time.time())
            
            # Recopilar estadísticas
            stats = {
                "cameras": {
                    "total": len(self.cameras),
                    "online": sum(1 for c in self.cameras.values() if c.get("status") == "online"),
                    "recording": sum(1 for c in self.cameras.values() if c.get("recording", False))
                },
                "events": {
                    "total": len(self.event_history),
                    "active_alerts": len(self.active_alerts),
                    "by_type": {},
                    "by_camera": {}
                },
                "storage": self.storage_manager.get_storage_usage(),
                "system": {
                    "uptime": time.time() - start_time,
                    "version": "1.0.0"
                }
            }
            
            # Conteo por tipo de evento
            for event in self.event_history:
                event_type = event.get("type", "unknown")
                if event_type not in stats["events"]["by_type"]:
                    stats["events"]["by_type"][event_type] = 0
                stats["events"]["by_type"][event_type] += 1
                
            # Conteo por cámara
            for event in self.event_history:
                camera_id = event.get("camera_id", "unknown")
                if camera_id not in stats["events"]["by_camera"]:
                    stats["events"]["by_camera"][camera_id] = 0
                stats["events"]["by_camera"][camera_id] += 1
            
            return jsonify(stats)
            
        except Exception as e:
            self.logger.error(f"Error al obtener estadísticas: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_specific_statistics(self, stat_type):
        """Obtener estadísticas específicas"""
        try:
            if stat_type == "detections":
                # Estadísticas de detecciones por cámara
                stats = {}
                for camera_id, analyzer in self.analyzers.items():
                    camera_name = self.cameras.get(camera_id, {}).get("name", camera_id)
                    stats[camera_id] = {
                        "name": camera_name,
                        "object_counts": {
                            "person": analyzer.get_object_count("person"),
                            "vehicle": analyzer.get_object_count(["car", "truck", "bus"]),
                            "total": analyzer.get_object_count()
                        },
                        "zone_counts": analyzer.get_zone_counts()
                    }
                    
                return jsonify(stats)
                
            elif stat_type == "alerts":
                # Estadísticas de alertas
                stats = {
                    "total": len(self.event_history),
                    "active": len(self.active_alerts),
                    "by_type": {},
                    "by_camera": {},
                    "by_hour": [0] * 24,
                    "recent_trend": []
                }
                
                # Conteo por tipo y cámara
                for event in self.event_history:
                    event_type = event.get("type", "unknown")
                    if event_type not in stats["by_type"]:
                        stats["by_type"][event_type] = 0
                    stats["by_type"][event_type] += 1
                    
                    camera_id = event.get("camera_id", "unknown")
                    if camera_id not in stats["by_camera"]:
                        stats["by_camera"][camera_id] = 0
                    stats["by_camera"][camera_id] += 1
                    
                    # Distribución por hora
                    try:
                        timestamp = datetime.fromisoformat(event.get("timestamp", ""))
                        hour = timestamp.hour
                        stats["by_hour"][hour] += 1
                    except:
                        pass
                
                # Tendencia reciente (últimos 7 días por día)
                now = datetime.now()
                for i in range(7):
                    day = (now - timedelta(days=i)).date()
                    day_count = 0
                    
                    for event in self.event_history:
                        try:
                            event_date = datetime.fromisoformat(event.get("timestamp", "")).date()
                            if event_date == day:
                                day_count += 1
                        except:
                            pass
                    
                    stats["recent_trend"].insert(0, {
                        "date": day.isoformat(),
                        "count": day_count
                    })
                
                return jsonify(stats)
                
            elif stat_type == "storage":
                # Estadísticas de almacenamiento
                return jsonify(self.storage_manager.get_detailed_storage_stats())
                
            else:
                return jsonify({"error": f"Tipo de estadística no reconocido: {stat_type}"}), 400
            
        except Exception as e:
            self.logger.error(f"Error al obtener estadísticas específicas: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_zones(self, camera_id):
        """Obtener zonas definidas para una cámara"""
        try:
            if camera_id not in self.analyzers:
                return jsonify({"error": "Cámara no encontrada"}), 404
                
            analyzer = self.analyzers[camera_id]
            zones = analyzer.config.get("zones", {})
            
            return jsonify(zones)
            
        except Exception as e:
            self.logger.error(f"Error al obtener zonas para cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def create_zone(self, camera_id):
        """Crear nueva zona para una cámara"""
        try:
            if camera_id not in self.analyzers:
                return jsonify({"error": "Cámara no encontrada"}), 404
                
            # Obtener datos
            data = request.json
            if not data or "name" not in data or "polygon" not in data:
                return jsonify({"error": "Datos incompletos"}), 400
                
            zone_name = data["name"]
            polygon = data["polygon"]
            color = data.get("color", (0, 255, 0))  # Verde por defecto
            
            # Validar polígono
            if not isinstance(polygon, list) or len(polygon) < 3:
                return jsonify({"error": "El polígono debe tener al menos 3 puntos"}), 400
                
            # Crear zona
            analyzer = self.analyzers[camera_id]
            analyzer.set_zone_definition(zone_name, polygon, color)
            
            # Guardar cambios en configuración
            if camera_id in self.config.get("cameras", {}):
                camera_config = self.config["cameras"][camera_id]
                if "analyzer" not in camera_config:
                    camera_config["analyzer"] = {}
                if "zones" not in camera_config["analyzer"]:
                    camera_config["analyzer"]["zones"] = {}
                    
                camera_config["analyzer"]["zones"][zone_name] = {
                    "polygon": polygon,
                    "color": color
                }
                
                self._save_config()
            
            return jsonify({
                "status": "success",
                "message": f"Zona '{zone_name}' creada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al crear zona para cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def update_zone(self, camera_id, zone_id):
        """Actualizar zona existente"""
        try:
            if camera_id not in self.analyzers:
                return jsonify({"error": "Cámara no encontrada"}), 404
                
            analyzer = self.analyzers[camera_id]
            zones = analyzer.config.get("zones", {})
            
            if zone_id not in zones:
                return jsonify({"error": f"Zona '{zone_id}' no encontrada"}), 404
                
            # Obtener datos
            data = request.json
            if not data:
                return jsonify({"error": "Datos no válidos"}), 400
                
            # Actualizar polígono si está presente
            if "polygon" in data:
                polygon = data["polygon"]
                if not isinstance(polygon, list) or len(polygon) < 3:
                    return jsonify({"error": "El polígono debe tener al menos 3 puntos"}), 400
                    
                color = data.get("color", zones[zone_id].get("color"))
                analyzer.set_zone_definition(zone_id, polygon, color)
                
            # Actualizar configuración
            if camera_id in self.config.get("cameras", {}):
                camera_config = self.config["cameras"][camera_id]
                if "analyzer" in camera_config and "zones" in camera_config["analyzer"]:
                    if zone_id in camera_config["analyzer"]["zones"]:
                        if "polygon" in data:
                            camera_config["analyzer"]["zones"][zone_id]["polygon"] = data["polygon"]
                        if "color" in data:
                            camera_config["analyzer"]["zones"][zone_id]["color"] = data["color"]
                            
                        self._save_config()
            
            return jsonify({
                "status": "success",
                "message": f"Zona '{zone_id}' actualizada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al actualizar zona {zone_id} para cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def delete_zone(self, camera_id, zone_id):
        """Eliminar zona"""
        try:
            if camera_id not in self.analyzers:
                return jsonify({"error": "Cámara no encontrada"}), 404
                
            analyzer = self.analyzers[camera_id]
            
            # Eliminar zona
            success = analyzer.delete_zone(zone_id)
            if not success:
                return jsonify({"error": f"Zona '{zone_id}' no encontrada"}), 404
                
            # Actualizar configuración
            if camera_id in self.config.get("cameras", {}):
                camera_config = self.config["cameras"][camera_id]
                if "analyzer" in camera_config and "zones" in camera_config["analyzer"]:
                    if zone_id in camera_config["analyzer"]["zones"]:
                        del camera_config["analyzer"]["zones"][zone_id]
                        self._save_config()
            
            return jsonify({
                "status": "success",
                "message": f"Zona '{zone_id}' eliminada correctamente"
            })
            
        except Exception as e:
            self.logger.error(f"Error al eliminar zona {zone_id} para cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_camera_stream(self, camera_id):
        """Obtener stream MJPEG de una cámara"""
        try:
            if camera_id not in self.cameras:
                return jsonify({"error": "Cámara no encontrada"}), 404
                
            if self.cameras[camera_id].get("status") != "online":
                return jsonify({"error": "Cámara no disponible"}), 503
                
            # Implementar streaming MJPEG
            def generate_frames():
                while True:
                    # Obtener frame
                    stream = self.camera_streams.get(camera_id)
                    if not stream:
                        break
                        
                    frame = stream.get("last_frame")
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Comprimir a JPEG
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    
                    # Formato MJPEG
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                    
                    # Limitar FPS del stream
                    time.sleep(0.033)  # ~30 FPS
            
            return Response(
                generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
            
        except Exception as e:
            self.logger.error(f"Error al obtener stream de cámara {camera_id}: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_learning_status(self):
        """Obtener estado del sistema de aprendizaje"""
        try:
            status = {
                "client_id": self.learning_system.client_id,
                "event_count": len(self.learning_system.event_history),
                "models": {
                    model_type: {"available": True}
                    for model_type in self.learning_system.behavior_models
                },
                "thresholds": self.learning_system.detection_thresholds,
                "high_risk_zones": [
                    zone_id for zone_id, profile in self.learning_system.zone_risk_profiles.items()
                    if profile.get('risk_level', 0) > 50
                ]
            }
            
            return jsonify(status)
        except Exception as e:
            self.logger.error(f"Error al obtener estado de aprendizaje: {e}")
            return jsonify({"error": str(e)}), 500
    
    def train_models(self):
        """Iniciar entrenamiento de modelos"""
        try:
            data = request.json or {}
            specific_model = data.get('model_type')
            
            results = self.learning_system.train_models(specific_model)
            
            return jsonify({
                "status": "success",
                "results": results
            })
        except Exception as e:
            self.logger.error(f"Error al entrenar modelos: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_optimized_parameters(self):
        """Obtener parámetros optimizados"""
        try:
            camera_id = request.args.get('camera_id')
            zone_id = request.args.get('zone_id')
            event_type = request.args.get('event_type')
            
            params = self.learning_system.get_optimized_parameters(
                camera_id=camera_id,
                zone_id=zone_id,
                event_type=event_type
            )
            
            return jsonify(params)
        except Exception as e:
            self.logger.error(f"Error al obtener parámetros optimizados: {e}")
            return jsonify({"error": str(e)}), 500
    
    def run_simulation(self):
        """Ejecutar simulación para entrenamiento"""
        try:
            data = request.json
            if not data:
                return jsonify({"error": "Configuración de simulación requerida"}), 400
            
            results = self.learning_system.run_scenario_simulation(data)
            
            return jsonify(results)
        except Exception as e:
            self.logger.error(f"Error al ejecutar simulación: {e}")
            return jsonify({"error": str(e)}), 500
    
    def register_feedback(self, event_id):
        """Registrar retroalimentación para un evento"""
        try:
            data = request.json
            if not data or 'feedback' not in data:
                return jsonify({"error": "Retroalimentación requerida"}), 400
            
            feedback = data.get('feedback')
            if feedback not in ['true_positive', 'false_positive', 'not_sure']:
                return jsonify({"error": "Valor de retroalimentación inválido"}), 400
            
            # Buscar evento
            event_data = None
            for event in self.event_history:
                if event.get('id') == event_id:
                    event_data = event
                    break
                
            if not event_data:
                return jsonify({"error": "Evento no encontrado"}), 404
            
            # Registrar retroalimentación
            self.learning_system.register_event(event_data, feedback)
            
            return jsonify({
                "status": "success",
                "message": "Retroalimentación registrada correctamente"
            })
        except Exception as e:
            self.logger.error(f"Error al registrar retroalimentación: {e}")
            return jsonify({"error": str(e)}), 500
    
    def get_watchlist(self):
        """Obtener lista de personas en lista de vigilancia"""
        try:
            # Obtener todas las personas
            persons = self.face_recognition_system.get_all_persons()
            
            # Filtrar solo las que están en lista de vigilancia
            watchlist = [p for p in persons if p.get('watch_list', False)]
            
            # Excluir datos de embeddings para aligerar respuesta
            for person in watchlist:
                if 'embedding' in person:
                    del person['embedding']
                    
            return jsonify(watchlist)
        except Exception as e:
            self.logger.error(f"Error al obtener lista de vigilancia: {e}")
            return jsonify({"error": str(e)}), 500
    
    def add_to_watchlist(self, person_id):
        """Añadir persona a la lista de vigilancia"""
        try:
            # Verificar si la persona existe
            person = self.face_recognition_system.get_person(person_id)
            if not person:
                return jsonify({"error": "Persona no encontrada"}), 404
            
            # Obtener datos adicionales
            data = request.json or {}
            alert_level = data.get('alert_level', 'high')
            notes = data.get('notes', '')
            
            # Actualizar información
            updated_info = {
                'watch_list': True,
                'watch_list_date': datetime.now().isoformat(),
                'watch_list_alert_level': alert_level,
                'watch_list_notes': notes
            }
            
            result = self.face_recognition_system.update_person_info(person_id, updated_info)
            
            if not result:
                return jsonify({"error": "No se pudo añadir a la lista de vigilancia"}), 500
            
            return jsonify({
                "status": "success",
                "message": f"Persona {person_id} añadida a la lista de vigilancia"
            })
        except Exception as e:
            self.logger.error(f"Error al añadir persona {person_id} a lista de vigilancia: {e}")
            return jsonify({"error": str(e)}), 500
    
    def remove_from_watchlist(self, person_id):
        """Eliminar persona de la lista de vigilancia"""
        try:
            # Verificar si la persona existe
            person = self.face_recognition_system.get_person(person_id)
            if not person:
                return jsonify({"error": "Persona no encontrada"}), 404
            
            # Actualizar información
            updated_info = {
                'watch_list': False,
                'watch_list_removed_date': datetime.now().isoformat()
            }
            
            result = self.face_recognition_system.update_person_info(person_id, updated_info)
            
            if not result:
                return jsonify({"error": "No se pudo eliminar de la lista de vigilancia"}), 500
            
            return jsonify({
                "status": "success",
                "message": f"Persona {person_id} eliminada de la lista de vigilancia"
            })
        except Exception as e:
            self.logger.error(f"Error al eliminar persona {person_id} de lista de vigilancia: {e}")
            return jsonify({"error": str(e)}), 500
    
    def run(self, host=None, port=None, debug=None):
        """Iniciar la API REST"""
        # Guardar tiempo de inicio
        self.start_time = time.time()
        
        # Obtener configuración de API
        api_config = self.config.get("api", {})
        
        # Usar valores de parámetros o de configuración
        host = host or api_config.get("host", "0.0.0.0")
        port = port or api_config.get("port", 5000)
        debug = debug if debug is not None else api_config.get("debug", False)
        
        self.logger.info(f"Iniciando API REST en {host}:{port}")
        
        try:
            # Iniciar aplicación Flask
            self.app.run(host=host, port=port, debug=debug, threaded=True)
        except KeyboardInterrupt:
            self.logger.info("API REST detenida por el usuario")
        except Exception as e:
            self.logger.error(f"Error al iniciar API REST: {e}")
        finally:
            # Limpiar recursos
            self.running = False
            if self.bg_thread.is_alive():
                self.bg_thread.join(timeout=2.0)
                
            self.logger.info("Recursos liberados")


if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Cargar ruta de configuración desde argumentos o usar valor por defecto
    import argparse
    parser = argparse.ArgumentParser(description='API REST para sistema de vigilancia')
    parser.add_argument('--config', type=str, default='configs/system.json',
                        help='Ruta al archivo de configuración')
    args = parser.parse_args()
    
    # Inicializar y ejecutar API
    api = SurveillanceAPI(config_path=args.config)
    api.run() 