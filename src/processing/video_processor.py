import os
import cv2
import time
import asyncio
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO
from ultralytics.utils.ops import non_max_suppression
# from bytetrack.byte_tracker import BYTETracker
import torch

from src.events.event_bus import EventBus, EventTypes
from src.database.models import Camera, Zone, Alert, DetectedObject
from src.database.db import get_db
from src.config.config_loader import load_config

class VideoProcessor:
    """
    Procesador de video para detección, tracking y análisis de comportamiento
    Integra la detección de objetos (YOLO), tracking (ByteTrack) y análisis de zonas
    """
    
    def __init__(self, camera_id: int, config_path: str = "configs/config.yaml", event_bus: Optional[EventBus] = None):
        """Inicializa el procesador para una cámara específica"""
        self.camera_id = camera_id
        self.logger = logging.getLogger(f"VideoProcessor-Cam{camera_id}")
        
        # Cargar configuración
        self.config = load_config(config_path)
        
        # Estado de procesamiento
        self.is_running = False
        self.current_frame = None
        self.frame_count = 0
        self.fps = 0
        self.start_time = 0
        self.detection_objects = []
        self.tracked_objects = {}  # ID: {track_info}
        self.zones = []
        self.zone_counts = {}
        
        # Bus de eventos
        self.event_bus = event_bus
        
        # Detector, Tracker y otros componentes se inicializarán bajo demanda
        self.detector = None
        self.tracker = None
        self.capture = None
        self.camera_info = None
        self.recording = None
        
    async def initialize(self):
        """Inicializa los componentes necesarios para el procesamiento"""
        try:
            # Cargar información de la cámara desde la base de datos
            with get_db() as db:
                self.camera_info = db.query(Camera).filter(Camera.id == self.camera_id).first()
                if not self.camera_info:
                    self.logger.error(f"No se encontró la cámara con ID {self.camera_id}")
                    return False
                
                # Cargar zonas asociadas a la cámara
                self.zones = db.query(Zone).filter(Zone.camera_id == self.camera_id, Zone.is_active == True).all()
                self.logger.info(f"Cargadas {len(self.zones)} zonas para la cámara {self.camera_id}")
            
            # Inicializar detector
            det_config = self.config["detection"]
            model_path = os.path.join(self.config["storage"]["models_dir"], det_config["default_model"])
            
            # Verificar si existe un modelo específico para esta cámara
            cam_model = self.camera_info.config.get("model")
            if cam_model and os.path.exists(os.path.join(self.config["storage"]["models_dir"], cam_model)):
                model_path = os.path.join(self.config["storage"]["models_dir"], cam_model)
            
            # Cargar modelo
            self.logger.info(f"Cargando modelo de detección: {model_path}")
            self.detector = YOLO(model_path)
            
            # Configurar tracker
            # self.tracker = BYTETracker(
            #     track_thresh=det_config["confidence_threshold"],
            #     match_thresh=track_config["iou_threshold"],
            #     track_buffer=track_config["max_age"],
            #     frame_rate=self.camera_info.fps or 15
            # )
            
            # Inicializar evento de detección de movimiento
            self.motion_detector = None
            if self.config["agents"]["motion_detection"]["enabled"]:
                self.motion_detector = cv2.createBackgroundSubtractorMOG2(
                    history=self.config["agents"]["motion_detection"]["history"],
                    varThreshold=100 * self.config["agents"]["motion_detection"]["sensitivity"]
                )
            
            # Conexión al evento bus si no está ya conectado
            if self.event_bus is None:
                self.event_bus = EventBus(
                    redis_host=self.config["redis"]["host"],
                    redis_port=self.config["redis"]["port"],
                    redis_db=self.config["redis"]["db"],
                    redis_password=self.config["redis"]["password"],
                )
                await self.event_bus.connect()
            
            # Inicializar conteo por zonas
            for zone in self.zones:
                self.zone_counts[zone.id] = {}
            
            self.logger.info(f"Procesador de video inicializado para cámara {self.camera_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error inicializando el procesador de video: {e}")
            return False
    
    async def start(self):
        """Inicia el procesamiento de video"""
        if self.is_running:
            self.logger.warning("El procesador ya está en ejecución")
            return False
        
        if not self.detector or not self.camera_info:
            if not await self.initialize():
                self.logger.error("No se pudo inicializar el procesador")
                return False
        
        try:
            # Abrir captura de video
            self.capture = cv2.VideoCapture(self.camera_info.url)
            if not self.capture.isOpened():
                self.logger.error(f"No se pudo abrir la cámara: {self.camera_info.url}")
                return False
            
            # Iniciar procesamiento
            self.is_running = True
            self.frame_count = 0
            self.start_time = time.time()
            
            # Publicar evento de inicio
            await self.event_bus.publish(f"camera_{self.camera_id}_processing_started", {
                "camera_id": self.camera_id,
                "timestamp": datetime.now().isoformat(),
                "message": f"Iniciado procesamiento para cámara {self.camera_info.name}"
            })
            
            self.logger.info(f"Iniciado procesamiento para cámara {self.camera_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error iniciando el procesamiento: {e}")
            self.is_running = False
            return False
    
    async def _process_frame(self):
        """Procesa un solo frame del video"""
        try:
            ret, frame = self.capture.read()
            if not ret:
                self.logger.error("No se pudo leer el frame")
                return
            
            self.current_frame = frame
            self.frame_count += 1
            
            # Procesar detección
            results = self.detector.predict(frame, conf=self.config["detection"]["confidence_threshold"])
            self.detection_objects = results[0].boxes.xyxy.tolist()
            
            # Procesar tracking
            # tracked_objects = self.tracker.update(self.detection_objects)
            # self.tracked_objects = {track_id: track_info for track_id, track_info in tracked_objects}
            
            # Procesar análisis de zonas
            zone_events = await self._analyze_zones()
            
            # Procesar comportamiento
            loitering_events = await self._process_loitering()
            
            # Actualizar conteo por zonas
            for zone in self.zones:
                self.zone_counts[zone.id] = {}
            
            self.logger.debug(f"Terminado análisis de zonas para frame {self.frame_count}")
            return zone_events, loitering_events
        except Exception as e:
            self.logger.error(f"Error procesando frame: {e}")
            return [], []
    
    async def _analyze_zones(self):
        """Analiza comportamiento de objetos en zonas"""
        try:
            zone_events = []
            for zone in self.zones:
                zone_events.append({
                    "zone_id": zone.id,
                    "zone_name": zone.name,
                    "timestamp": datetime.now().isoformat()
                })
            
            self.logger.debug(f"Terminado análisis de zonas para frame {self.frame_count}")
            return zone_events
        except Exception as e:
            self.logger.error(f"Error analizando zonas: {e}")
            return []
    
    async def _process_loitering(self, timeout: int = None):
        """Analiza comportamiento de merodeo (objetos que permanecen demasiado tiempo)"""
        if not timeout:
            timeout = self.config["behavior"]["loitering_time_threshold"]
        
        loitering_events = []
        current_time = time.time()
        
        for track_id, track_info in self.tracked_objects.items():
            # Solo analizar personas
            if track_info["class_name"] != "person":
                continue
            
            # Verificar tiempo de permanencia
            if "first_seen" in track_info and (current_time - track_info["first_seen"]) > timeout:
                # Verificar si ya se generó alerta de merodeo para este objeto
                if not track_info.get("loitering_alert_sent", False):
                    loitering_event = {
                        "track_id": track_id,
                        "class_id": track_info["class_id"],
                        "class_name": track_info["class_name"],
                        "position": track_info["position"],
                        "duration": current_time - track_info["first_seen"],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Marcar como alerta enviada
                    self.tracked_objects[track_id]["loitering_alert_sent"] = True
                    
                    loitering_events.append(loitering_event)
                    
                    self.logger.info(f"Detectado merodeo: ID {track_id}, duración {current_time - track_info['first_seen']:.1f}s")
        
        return loitering_events
    
    def draw_results(self, frame=None):
        """Dibuja resultados de detección, tracking y zonas en el frame"""
        if frame is None:
            frame = self.current_frame.copy()
        if frame is None:
            return None
        
        # Dibujar objetos detectados y trayectorias
        for track_id, track_info in self.tracked_objects.items():
            # Dibujar bounding box
            x1, y1, x2, y2 = track_info["bbox"]
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), track_info["color"], 2)
            
            # Dibujar etiqueta
            label = f"{track_info['class_name']} {track_info['confidence']:.2f}"
            cv2.putText(frame, label, (int(x1), int(y1-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, track_info["color"], 2)
            
            # Dibujar ID
            cv2.putText(frame, str(track_id), (int(x1), int(y1-25)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Dibujar trayectoria
            if "trajectory" in track_info and len(track_info["trajectory"]) > 1:
                for i in range(1, len(track_info["trajectory"])):
                    pt1 = track_info["trajectory"][i-1]
                    pt2 = track_info["trajectory"][i]
                    cv2.line(frame, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), track_info["color"], 2)
        
        # Dibujar zonas
        for zone in self.zones:
            points = zone.points
            if not points or len(points) < 3:
                continue
            
            # Convertir puntos a formato numpy para dibujo
            pts = np.array(points, np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            # Determinar color según el tipo de zona
            color = (0, 0, 255)  # Rojo por defecto
            if zone.color:
                # Convertir el color de string a tupla BGR
                if zone.color == "red":
                    color = (0, 0, 255)
                elif zone.color == "green":
                    color = (0, 255, 0)
                elif zone.color == "blue":
                    color = (255, 0, 0)
                elif zone.color == "yellow":
                    color = (0, 255, 255)
            
            # Dibujar polígono
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Dibujar nombre de la zona
            if len(points) > 0:
                cv2.putText(frame, zone.name, (points[0][0], points[0][1]-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Dibujar conteo si existe
            if zone.id in self.zone_counts and self.zone_counts[zone.id]:
                count_text = " ".join([f"{k}:{v}" for k, v in self.zone_counts[zone.id].items()])
                if len(points) > 1:
                    cv2.putText(frame, count_text, (points[1][0], points[1][1]-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Mostrar FPS
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame 