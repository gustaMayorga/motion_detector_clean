from typing import List, Dict, Any, Tuple
import numpy as np
from dataclasses import dataclass
import cv2
from .object_detection import Detection

@dataclass
class Track:
    id: int
    detection: Detection
    kalman_filter: cv2.KalmanFilter
    history: List[Detection] = None
    age: int = 0
    hits: int = 0
    time_since_update: int = 0

class ObjectTracker:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_age = config.get('max_age', 30)
        self.min_hits = config.get('min_hits', 3)
        self.iou_threshold = config.get('iou_threshold', 0.3)
        
        # Almacena los tracks activos
        self.tracks: List[Track] = []
        self.next_id = 1
        
    def update(self, detections: List[Detection]) -> List[Track]:
        """Actualiza los tracks con nuevas detecciones"""
        # Si no hay tracks, inicializarlos
        if not self.tracks:
            return self._init_tracks(detections)
            
        # Si no hay detecciones, actualizar tracks existentes
        if not detections:
            return self._update_tracks([])
            
        # Calcular matriz de IoU
        match_matrix = self._calculate_iou_matrix(detections)
        
        # Asociar detecciones a tracks
        matches, unmatched_tracks, unmatched_detections = self._associate_detections(match_matrix)
        
        # Actualizar tracks con detecciones asignadas
        for track_idx, detection_idx in matches:
            self._update_matched_track(self.tracks[track_idx], detections[detection_idx])
            
        # Actualizar tracks sin detecciones
        for track_idx in unmatched_tracks:
            self._update_unmatched_track(self.tracks[track_idx])
            
        # Inicializar nuevos tracks para detecciones sin asignar
        for detection_idx in unmatched_detections:
            self._init_new_track(detections[detection_idx])
            
        # Eliminar tracks viejos
        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age]
        
        # Retornar solo tracks confirmados
        return [t for t in self.tracks if t.hits >= self.min_hits]
        
    def _init_tracks(self, detections: List[Detection]) -> List[Track]:
        """Inicializa tracks para un conjunto de detecciones"""
        self.tracks = []
        
        for detection in detections:
            self._init_new_track(detection)
            
        # No retornar tracks hasta que sean confirmados
        return []
        
    def _init_new_track(self, detection: Detection):
        """Inicializa un nuevo track para una detección"""
        # Configurar Kalman filter
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                       [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                      [0, 1, 0, 1],
                                      [0, 0, 1, 0],
                                      [0, 0, 0, 1]], np.float32)
        
        # Posición inicial
        x1, y1, x2, y2 = detection.bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        kf.statePost = np.array([[center_x],
                             [center_y],
                             [0],  # velocidad x
                             [0]], np.float32)  # velocidad y
        
        # Crear track
        self.tracks.append(Track(
            id=self.next_id,
            detection=detection,
            kalman_filter=kf,
            history=[detection],
            hits=1
        ))
        
        # Incrementar ID
        self.next_id += 1
        
    def _calculate_iou_matrix(self, detections: List[Detection]) -> np.ndarray:
        """Calcula la matriz de IoU entre tracks y detecciones"""
        n_tracks = len(self.tracks)
        n_detections = len(detections)
        
        iou_matrix = np.zeros((n_tracks, n_detections))
        
        for i, track in enumerate(self.tracks):
            for j, detection in enumerate(detections):
                iou_matrix[i, j] = self._calculate_iou(track.detection.bbox, detection.bbox)
                
        return iou_matrix
        
    def _calculate_iou(self, bbox1: Tuple[int, int, int, int], 
                     bbox2: Tuple[int, int, int, int]) -> float:
        """Calcula IoU entre dos bounding boxes"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calcular área de intersección
        xx1 = max(x1_1, x1_2)
        yy1 = max(y1_1, y1_2)
        xx2 = min(x2_1, x2_2)
        yy2 = min(y2_1, y2_2)
        
        # Intersección
        w = max(0, xx2 - xx1)
        h = max(0, yy2 - yy1)
        intersection = w * h
        
        # Unión
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        # IoU
        iou = intersection / max(union, 1e-6)
        
        return iou
        
    def _associate_detections(self, iou_matrix: np.ndarray):
        """Asocia detecciones a tracks usando IoU"""
        n_tracks, n_detections = iou_matrix.shape
        
        # Lista de pares (track_idx, detection_idx)
        matches = []
        
        # Track y detección sin emparejar
        unmatched_tracks = list(range(n_tracks))
        unmatched_detections = list(range(n_detections))
        
        # Para cada track, encontrar la mejor detección
        for t in range(n_tracks):
            if len(unmatched_detections) == 0:
                break
                
            # Obtener mejor match para este track
            best_match = -1
            best_iou = self.iou_threshold
            
            for d in unmatched_detections:
                iou = iou_matrix[t, d]
                if iou > best_iou:
                    best_iou = iou
                    best_match = d
                    
            if best_match >= 0:
                matches.append((t, best_match))
                unmatched_tracks.remove(t)
                unmatched_detections.remove(best_match)
                
        return matches, unmatched_tracks, unmatched_detections
        
    def _update_matched_track(self, track: Track, detection: Detection):
        """Actualiza un track con una detección emparejada"""
        x1, y1, x2, y2 = detection.bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Actualizar Kalman filter
        track.kalman_filter.correct(np.array([[center_x], [center_y]], np.float32))
        
        # Actualizar track
        track.detection = detection
        track.history.append(detection)
        track.hits += 1
        track.time_since_update = 0
        track.age += 1
        
    def _update_unmatched_track(self, track: Track):
        """Actualiza un track sin detección emparejada"""
        # Predicción de Kalman
        predicted_state = track.kalman_filter.predict()
        
        # Crear bbox actualizado basado en la predicción
        center_x = predicted_state[0, 0]
        center_y = predicted_state[1, 0]
        
        # Obtener ancho y alto del bbox actual
        x1, y1, x2, y2 = track.detection.bbox
        width = x2 - x1
        height = y2 - y1
        
        # Crear nuevo bbox centrado en la posición predicha
        new_x1 = int(center_x - width / 2)
        new_y1 = int(center_y - height / 2)
        new_x2 = int(center_x + width / 2)
        new_y2 = int(center_y + height / 2)
        
        # Actualizar detección simulada
        track.detection = Detection(
            bbox=(new_x1, new_y1, new_x2, new_y2),
            class_id=track.detection.class_id,
            class_name=track.detection.class_name,
            confidence=track.detection.confidence * 0.9,  # Disminuir confianza
            frame_id=track.detection.frame_id + 1
        )
        
        # Actualizar estado
        track.time_since_update += 1
        track.age += 1
        
    def _update_tracks(self, matched_detections: List[Detection]) -> List[Track]:
        """Actualiza todos los tracks sin nuevas detecciones"""
        for track in self.tracks:
            track.time_since_update += 1
            track.age += 1
            
        # Eliminar tracks viejos
        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age]
        
        # Retornar solo tracks confirmados
        return [t for t in self.tracks if t.hits >= self.min_hits]

__all__ = ['Track', 'ObjectTracker'] 