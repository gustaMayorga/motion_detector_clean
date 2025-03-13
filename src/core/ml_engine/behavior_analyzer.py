from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
from .object_tracking import Track
import cv2

@dataclass
class BehaviorPattern:
    pattern_type: str
    confidence: float
    details: Dict[str, Any]
    track_ids: List[int]
    timestamp: datetime

class BehaviorAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pattern_history: List[BehaviorPattern] = []
        self.track_history: Dict[int, List[Tuple[datetime, np.ndarray]]] = {}
        self.max_history = config.get('max_history_seconds', 30)
        self.loitering_area_threshold = config.get('loitering_area_threshold', 5000)
        self.group_distance_threshold = config.get('group_distance_threshold', 100)
        
    def analyze_tracks(self, tracks: List[Track], current_time: datetime) -> List[BehaviorPattern]:
        """Analiza los tracks para detectar patrones de comportamiento"""
        # Quitar el async ya que no es necesario
        if not tracks:
            return []
        
        patterns = []
        
        # Detectar patrones
        if loitering := self._detect_loitering(tracks):
            patterns.append(loitering)
        
        if grouping := self._detect_grouping(tracks):
            patterns.append(grouping)
        
        return patterns
        
    def _detect_loitering(self, tracks: List[Track]) -> Optional[BehaviorPattern]:
        """Detecta comportamiento de merodeo"""
        for track in tracks:
            # Calcular área cubierta por el track
            area = self._calculate_track_area(track)
            
            # Si el área es menor que el umbral, puede ser merodeo
            if area < self.loitering_area_threshold:
                return BehaviorPattern(
                    pattern_type="loitering",
                    confidence=0.7,
                    details={
                        "area": float(area),
                        "track_id": track.id
                    },
                    track_ids=[track.id],
                    timestamp=datetime.now()
                )
        return None
        
    def _detect_grouping(self, tracks: List[Track]) -> Optional[BehaviorPattern]:
        """Detecta formación de grupos"""
        if len(tracks) < 2:
            return None
        
        # Calcular centros de los tracks
        centers = []
        for track in tracks:
            x1, y1, x2, y2 = track.detection.bbox
            center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
            centers.append(center)
        
        # Buscar tracks cercanos
        groups = []
        for i, center1 in enumerate(centers):
            group = [i]
            for j, center2 in enumerate(centers[i+1:], i+1):
                distance = np.linalg.norm(center1 - center2)
                if distance < self.group_distance_threshold:
                    group.append(j)
            if len(group) > 1:
                groups.append(group)
        
        # Si encontramos un grupo
        if groups:
            # Usar el grupo más grande
            largest_group = max(groups, key=len)
            group_track_ids = [tracks[i].id for i in largest_group]
            
            return BehaviorPattern(
                pattern_type="group_formation",
                confidence=0.8,
                details={
                    "group_size": len(group_track_ids),
                    "distance_threshold": self.group_distance_threshold
                },
                track_ids=group_track_ids,
                timestamp=datetime.now()
            )
        
        return None
    
    def _calculate_track_area(self, track: Track) -> float:
        """
        Calcula el área cubierta por un track
        """
        x1, y1, x2, y2 = track.detection.bbox
        return (x2 - x1) * (y2 - y1)