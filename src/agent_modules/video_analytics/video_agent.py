import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from src.agent_modules.base.agent_base import BaseAgent, AgentConfig
from src.core.ml_engine.object_detection import ObjectDetector, Detection
from src.core.ml_engine.object_tracking import ObjectTracker, Track
from src.core.ml_engine.behavior_analyzer import BehaviorAnalyzer, BehaviorPattern
from src.core.event_system.event_bus import Event
from datetime import datetime
from pathlib import Path
from src.services.video_recorder.recorder import VideoRecorder

class VideoAnalyticsAgent(BaseAgent):
    def __init__(self, config: Dict[str, Any], event_bus=None, logger=None):
        # Crear objetos mock si no se proporcionan
        if event_bus is None:
            from src.core.event_system import EventBus
            event_bus = EventBus()
        
        if logger is None:
            from src.utils.logging import SecurityLogger
            logger = SecurityLogger({'log_dir': 'logs'})
        
        super().__init__(config, event_bus, logger)
        
        # Inicializar componentes con valores predeterminados si no existen
        self.detector = ObjectDetector(config.get('object_detection', {}), test_mode=True)
        self.tracker = ObjectTracker(config.get('object_tracking', {}))
        self.analyzer = BehaviorAnalyzer(config.get('behavior_analysis', {}))
        
        # Configuración de video con valores predeterminados
        self.video_config = config.get('video_processing', {
            'frame_skip': 1,
            'resize_width': 640,
            'resize_height': 480
        })
        
        # Inicializar recorder sólo si está en el config
        if 'recording' in config:
            self.recorder = VideoRecorder(config['recording'])
        else:
            # Usar valores predeterminados para grabación
            default_recording_config = {
                'storage_path': 'recordings',
                'fps': 15,
                'max_duration_minutes': 10,
                'enabled': False
            }
            self.recorder = VideoRecorder(default_recording_config)
        
        # Completar inicialización de variables restantes
        self.frame_count = 0
        self.cap = None
        self.zones = self._setup_zones(config.get('zones', []))
        
        # Estado del procesamiento
        self.active_tracks = {}
        self.last_frame_time = None
        
        self.current_recording = None
        self.recording_events = []
        
    async def start(self):
        """Inicia el procesamiento de video"""
        await super().start()
        
        try:
            self.cap = cv2.VideoCapture(self.config['video_source'])
            if not self.cap.isOpened():
                raise RuntimeError(f"No se pudo abrir la fuente de video: {self.config['video_source']}")
                
            self.logger.logger.info(f"Iniciando análisis de video en {self.config['video_source']}")
            
            while self.running:
                await self._process_frame()
                
        except Exception as e:
            await self.handle_error(e)
            
        finally:
            if self.cap:
                self.cap.release()
                
    async def _process_frame(self):
        """Procesa un frame de video"""
        # Saltar frames según configuración
        if self.frame_count % self.video_config['frame_skip'] != 0:
            self.frame_count += 1
            return
            
        ret, frame = self.cap.read()
        if not ret:
            await self.stop()
            return
            
        try:
            # Preprocesar frame
            frame = self._preprocess_frame(frame)
            
            # Detección de objetos
            detections = await self.detector.detect(frame, self.frame_count)
            
            # Tracking
            tracks = self.tracker.update(detections)
            
            # Analizar zonas y reglas
            await self._analyze_tracks(tracks, frame)
            
            # Analizar comportamientos
            patterns = self.analyzer.analyze_tracks(tracks, datetime.now())
            if patterns:
                await self._handle_behavior_patterns(patterns, frame)
            
            # Actualizar estado
            self._update_tracking_state(tracks)
            
            # Gestionar grabación
            await self._handle_recording(frame, tracks)
            
            # Guardar frame procesado si está configurado
            if self.config.get('save_processed_frames', False):
                await self._save_processed_frame(frame, tracks)
                
            self.frame_count += 1
            
        except Exception as e:
            await self.handle_error(e, {"frame_id": self.frame_count})
            
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocesa el frame para análisis"""
        # Redimensionar si está configurado
        if 'resize_width' in self.video_config:
            frame = cv2.resize(
                frame,
                (self.video_config['resize_width'], self.video_config['resize_height'])
            )
            
        return frame
        
    async def _analyze_tracks(self, tracks: List[Track], frame: np.ndarray):
        """Analiza los tracks contra las reglas definidas"""
        current_time = datetime.now()
        
        for track in tracks:
            track_id = track.id
            detection = track.detection
            
            # Verificar cada zona
            for zone in self.zones:
                if self._is_in_zone(detection.bbox, zone['points']):
                    for rule in zone['rules']:
                        violation = await self._check_rule_violation(
                            track, rule, zone, current_time
                        )
                        
                        if violation:
                            await self._handle_violation(violation, track, frame, zone)
                            
    def _is_in_zone(self, bbox: tuple, zone_points: List[List[int]]) -> bool:
        """Verifica si un bbox está dentro de una zona"""
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        return cv2.pointPolygonTest(
            np.array(zone_points, np.int32),
            (center_x, center_y),
            False
        ) >= 0
        
    async def _check_rule_violation(
        self, track: Track, rule: Dict[str, Any],
        zone: Dict[str, Any], current_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Verifica violaciones de reglas"""
        if track.detection.class_name not in rule['classes']:
            return None
            
        if track.detection.confidence < rule.get('min_confidence', 0.5):
            return None
            
        violation = None
        
        if rule['type'] == 'intrusion':
            # Verificar horario si está definido
            if 'schedule' in rule:
                if self._is_in_schedule(current_time, rule['schedule']):
                    violation = {
                        'type': 'intrusion',
                        'zone': zone['name'],
                        'confidence': track.detection.confidence
                    }
                    
        elif rule['type'] == 'loitering':
            # Verificar tiempo de permanencia
            if track.id in self.active_tracks:
                track_data = self.active_tracks[track.id]
                duration = (current_time - track_data['first_seen']).total_seconds()
                
                if duration > rule['max_time']:
                    violation = {
                        'type': 'loitering',
                        'zone': zone['name'],
                        'duration': duration,
                        'confidence': track.detection.confidence
                    }
                    
        return violation
        
    async def _handle_violation(
        self, violation: Dict[str, Any],
        track: Track,
        frame: np.ndarray,
        zone: Dict[str, Any]
    ):
        """Maneja una violación de regla detectada"""
        # Guardar snapshot
        snapshot_path = await self._save_violation_snapshot(frame, track, violation)
        
        # Emitir evento
        await self.emit_event(
            "security_violation",
            {
                "violation_type": violation['type'],
                "zone": zone['name'],
                "object_class": track.detection.class_name,
                "confidence": violation['confidence'],
                "snapshot_path": str(snapshot_path),
                "details": violation
            },
            priority=3
        )
        
        # Añadir evento a la grabación actual
        if self.current_recording:
            self.recording_events.append({
                "type": "violation",
                "violation_type": violation['type'],
                "timestamp": datetime.now().isoformat(),
                "details": {
                    "zone": zone['name'],
                    "object_class": track.detection.class_name,
                    "confidence": violation['confidence']
                }
            })
        
    async def _save_violation_snapshot(
        self, frame: np.ndarray,
        track: Track,
        violation: Dict[str, Any]
    ) -> Path:
        """Guarda una imagen de la violación detectada"""
        snapshots_dir = Path(self.config['snapshots_dir'])
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{violation['type']}_{timestamp}.jpg"
        path = snapshots_dir / filename
        
        # Dibujar información en el frame
        frame_copy = frame.copy()
        self.detector.draw_detections([track.detection], frame_copy)
        
        # Guardar imagen
        cv2.imwrite(str(path), frame_copy)
        
        return path
        
    def _is_in_schedule(self, current_time: datetime, schedule: str) -> bool:
        """Verifica si la hora actual está dentro del horario especificado"""
        start_time, end_time = schedule.split('-')
        current_hour = current_time.hour + current_time.minute / 60
        
        start_hour = float(start_time.split(':')[0])
        end_hour = float(end_time.split(':')[0])
        
        if end_hour < start_hour:  # Horario nocturno
            return current_hour >= start_hour or current_hour <= end_hour
        else:
            return start_hour <= current_hour <= end_hour
            
    def _setup_zones(self, zones_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Configura las zonas de monitoreo"""
        if not zones_config:
            # Devolver una zona predeterminada si no hay configuración
            return [{
                'name': 'default_zone',
                'points': [[0, 0], [640, 0], [640, 480], [0, 480]],
                'rules': []
            }]
        return zones_config
        
    def _update_tracking_state(self, tracks: List[Track]):
        """Actualiza el estado de tracking"""
        current_time = datetime.now()
        
        # Actualizar tracks existentes
        for track in tracks:
            if track.id not in self.active_tracks:
                self.active_tracks[track.id] = {
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'frames_visible': 1
                }
            else:
                self.active_tracks[track.id]['last_seen'] = current_time
                self.active_tracks[track.id]['frames_visible'] += 1
                
        # Limpiar tracks antiguos
        self.active_tracks = {
            track_id: data
            for track_id, data in self.active_tracks.items()
            if (current_time - data['last_seen']).total_seconds() < 60
        } 
        
    async def _handle_behavior_patterns(self, 
                                      patterns: List[BehaviorPattern],
                                      frame: np.ndarray):
        """Maneja patrones de comportamiento detectados"""
        for pattern in patterns:
            # Guardar snapshot
            snapshot_path = await self._save_pattern_snapshot(
                frame, pattern
            )
            
            # Emitir evento
            await self.emit_event(
                "suspicious_behavior",
                {
                    "pattern_type": pattern.pattern_type,
                    "confidence": pattern.confidence,
                    "details": pattern.details,
                    "track_ids": pattern.track_ids,
                    "snapshot_path": str(snapshot_path)
                },
                priority=4 if pattern.confidence > 0.8 else 3
            )
            
    async def _save_pattern_snapshot(self,
                                   frame: np.ndarray,
                                   pattern: BehaviorPattern) -> Path:
        """Guarda una imagen del patrón detectado"""
        snapshots_dir = Path(self.config['snapshots_dir'])
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"behavior_{pattern.pattern_type}_{timestamp}.jpg"
        path = snapshots_dir / filename
        
        # Dibujar información en el frame
        frame_copy = frame.copy()
        
        # Añadir texto descriptivo
        cv2.putText(
            frame_copy,
            f"{pattern.pattern_type.upper()} ({pattern.confidence:.2f})",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2
        )
        
        # Guardar imagen
        cv2.imwrite(str(path), frame_copy)
        
        return path 

    async def _handle_recording(self, frame: np.ndarray, tracks: List[Track]):
        """Gestiona la grabación de video"""
        should_record = self._should_record(tracks)
        
        if should_record and not self.current_recording:
            # Iniciar nueva grabación
            self.current_recording = await self.recorder.start_recording(
                camera_id=self.config['camera_id'],
                trigger_type='motion',
                frame=frame
            )
            self.recording_events = []
            
        if self.current_recording:
            # Añadir frame y eventos
            await self.recorder.add_frame(
                self.current_recording,
                frame,
                self.recording_events
            )
            self.recording_events = []
            
            if not should_record:
                # Detener grabación si ya no hay actividad
                await self.recorder.stop_recording(self.current_recording)
                self.current_recording = None
                
    def _should_record(self, tracks: List[Track]) -> bool:
        """Determina si se debe grabar basado en la actividad detectada"""
        if not self.config['recording'].get('enabled', True):
            return False
            
        # Verificar si hay suficientes objetos de interés
        relevant_tracks = [
            t for t in tracks
            if t.detection.class_name in self.config['recording'].get('trigger_classes', ['person'])
            and t.detection.confidence >= self.config['recording'].get('min_confidence', 0.5)
        ]
        
        return len(relevant_tracks) >= self.config['recording'].get('min_objects', 1) 

    async def process_event(self, event: Event):
        """Procesa eventos recibidos"""
        if event.event_type == 'zone_violation':
            # Procesar violación de zona
            await self._handle_zone_violation(event.data)
        elif event.event_type == 'suspicious_behavior':
            # Procesar comportamiento sospechoso
            await self._handle_suspicious_behavior(event.data) 

    async def _handle_zone_violation(self, data: Dict[str, Any]):
        """Maneja eventos de violación de zona"""
        try:
            # Registrar el evento
            await self.logger.log_event(
                'zone_violation_processed',
                {
                    'zone': data.get('zone'),
                    'violation_type': data.get('violation_type'),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # Si hay una grabación activa, añadir el evento
            if self.current_recording:
                self.recording_events.append({
                    'type': 'zone_violation',
                    'timestamp': datetime.now().isoformat(),
                    'details': data
                })
                
        except Exception as e:
            await self.handle_error(e, {'event_data': data})

    async def _handle_suspicious_behavior(self, data: Dict[str, Any]):
        """Maneja eventos de comportamiento sospechoso"""
        try:
            # Registrar el evento
            await self.logger.log_event(
                'suspicious_behavior_processed',
                {
                    'pattern_type': data.get('pattern_type'),
                    'confidence': data.get('confidence'),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # Si hay una grabación activa, añadir el evento
            if self.current_recording:
                self.recording_events.append({
                    'type': 'suspicious_behavior',
                    'timestamp': datetime.now().isoformat(),
                    'details': data
                })
                
        except Exception as e:
            await self.handle_error(e, {'event_data': data}) 

    async def process_frame(self, frame: np.ndarray, frame_id: int) -> Tuple[List[Detection], List[Track], List[BehaviorPattern]]:
        """Procesa un frame de video"""
        # Detección de objetos
        detections = await self.detector.detect(frame, frame_id)
        
        # Tracking de objetos
        tracks = self.tracker.update(detections)
        
        # Análisis de comportamiento
        patterns = self.analyzer.analyze_tracks(tracks, datetime.now())
        
        # Emitir eventos si se detectan patrones y tenemos event_bus
        if hasattr(self, 'event_bus') and self.event_bus:
            for pattern in patterns:
                await self.emit_event(
                    'behavior_detected',
                    {
                        'pattern': pattern.pattern_type,
                        'confidence': pattern.confidence,
                        'details': pattern.details,
                        'track_ids': pattern.track_ids
                    }
                )
            
        return detections, tracks, patterns 