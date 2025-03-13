from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from datetime import datetime
import cv2

@dataclass
class TrackedObject:
    object_id: int
    class_id: int
    class_name: str
    first_seen: datetime
    last_seen: datetime
    positions: List[Tuple[int, int]]  # Centro del objeto
    confidence: float
    lost_count: int = 0

class ObjectTracker:
    def __init__(self, max_lost_frames: int = 30):
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_id = 0
        self.max_lost_frames = max_lost_frames
        
    def update(self, detections: List[Dict[str, Any]]) -> List[TrackedObject]:
        """
        Actualiza el estado de los objetos trackeados
        Args:
            detections: Lista de detecciones del detector
        Returns:
            Lista de objetos trackeados activos
        """
        current_time = datetime.now()
        
        # Incrementar contador de frames perdidos para todos los objetos
        for obj in self.tracked_objects.values():
            obj.lost_count += 1
            
        # Actualizar objetos existentes y crear nuevos
        matched_detections = set()
        
        for detection in detections:
            bbox = detection['bbox']
            center = self._get_bbox_center(bbox)
            
            # Buscar el objeto más cercano
            closest_obj = self._find_closest_object(center)
            
            if closest_obj is not None:
                # Actualizar objeto existente
                closest_obj.positions.append(center)
                closest_obj.last_seen = current_time
                closest_obj.confidence = detection['confidence']
                closest_obj.lost_count = 0
                matched_detections.add(id(detection))
            else:
                # Crear nuevo objeto
                new_obj = TrackedObject(
                    object_id=self.next_id,
                    class_id=detection['class_id'],
                    class_name=detection['class_name'],
                    first_seen=current_time,
                    last_seen=current_time,
                    positions=[center],
                    confidence=detection['confidence']
                )
                self.tracked_objects[self.next_id] = new_obj
                self.next_id += 1
                
        # Eliminar objetos perdidos
        self._remove_lost_objects()
        
        return list(self.tracked_objects.values())
        
    def _get_bbox_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """Calcula el centro de un bbox"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
        
    def _find_closest_object(self, center: Tuple[int, int]) -> Optional[TrackedObject]:
        """Encuentra el objeto más cercano al centro dado"""
        min_dist = float('inf')
        closest_obj = None
        
        for obj in self.tracked_objects.values():
            if obj.lost_count > self.max_lost_frames:
                continue
                
            last_pos = obj.positions[-1]
            dist = np.sqrt((center[0] - last_pos[0])**2 + (center[1] - last_pos[1])**2)
            
            if dist < min_dist:
                min_dist = dist
                closest_obj = obj
                
        return closest_obj if min_dist < 100 else None
        
    def _remove_lost_objects(self):
        """Elimina objetos que se han perdido por mucho tiempo"""
        to_remove = []
        for obj_id, obj in self.tracked_objects.items():
            if obj.lost_count > self.max_lost_frames:
                to_remove.append(obj_id)
                
        for obj_id in to_remove:
            del self.tracked_objects[obj_id] 