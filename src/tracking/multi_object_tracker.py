import numpy as np
import cv2
from scipy.spatial import distance
from collections import OrderedDict

class MultiObjectTracker:
    def __init__(self, max_disappeared=40, tracker_type="centroid"):
        self.next_object_id = 0
        self.objects = OrderedDict()       # ID del objeto -> centroide
        self.disappeared = OrderedDict()   # ID del objeto -> contador de frames desaparecido
        self.bbox = OrderedDict()          # ID del objeto -> bounding box
        self.max_disappeared = max_disappeared
        self.tracker_type = tracker_type
        
    def register(self, centroid, bbox):
        """Registrar un nuevo objeto con su centroide y bbox"""
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.bbox[self.next_object_id] = bbox
        self.next_object_id += 1
        
    def deregister(self, object_id):
        """Eliminar un objeto del tracking"""
        del self.objects[object_id]
        del self.disappeared[object_id]
        del self.bbox[object_id]
        
    def _get_centroid(self, bbox):
        """Calcula el centroide a partir del bounding box"""
        # bbox formato: [x1, y1, x2, y2]
        cX = int((bbox[0] + bbox[2]) / 2.0)
        cY = int((bbox[1] + bbox[3]) / 2.0)
        return (cX, cY)
        
    def update(self, detections):
        """Actualizar trackers con nuevas detecciones"""
        # Si no hay detecciones, incrementar contador de desaparecidos
        if len(detections) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                
                # Eliminar si ha desaparecido por demasiados frames
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
                    
            # No hay centroides a actualizar
            return self.get_tracks()
            
        # Inicializar array de centroides de detecciones actuales
        input_centroids = np.zeros((len(detections), 2), dtype="int")
        input_bboxes = []
        
        # Obtener centroides y bboxes de cada detección
        for (i, detection) in enumerate(detections):
            bbox = detection['bbox']
            input_bboxes.append(bbox)
            input_centroids[i] = self._get_centroid(bbox)
            
        # Si no estamos rastreando ningún objeto, registrar todos
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i], input_bboxes[i])
                
        # Si ya estamos rastreando objetos, necesitamos emparejarlos
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())
            
            # Calcular distancias entre centroides existentes y nuevos
            D = distance.cdist(np.array(object_centroids), input_centroids)
            
            # Encontrar el objeto más cercano para cada detección nueva
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            
            # Manejar asignaciones
            used_rows = set()
            used_cols = set()
            
            for (row, col) in zip(rows, cols):
                # Si ya hemos examinado esta fila o columna, ignorarla
                if row in used_rows or col in used_cols:
                    continue
                    
                # Obtener ID del objeto y actualizar su centroide y bbox
                object_id = object_ids[row]
                self.objects[object_id] = input_centroids[col]
                self.bbox[object_id] = input_bboxes[col]
                self.disappeared[object_id] = 0
                
                # Marcar fila y columna como usadas
                used_rows.add(row)
                used_cols.add(col)
                
            # Encontrar filas no utilizadas (objetos perdidos)
            unused_rows = set(range(D.shape[0])).difference(used_rows)
            
            # Incrementar contador de desaparecidos para objetos no emparejados
            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
                    
            # Encontrar columnas no utilizadas (nuevos objetos)
            unused_cols = set(range(D.shape[1])).difference(used_cols)
            
            # Registrar nuevos objetos
            for col in unused_cols:
                self.register(input_centroids[col], input_bboxes[col])
                
        # Retornar objetos rastreados
        return self.get_tracks()
        
    def get_tracks(self):
        """Retornar objetos actualmente rastreados con sus IDs"""
        tracks = []
        for object_id, centroid in self.objects.items():
            bbox = self.bbox[object_id]
            tracks.append({
                'id': object_id,
                'centroid': centroid,
                'bbox': bbox,
                'disappeared': self.disappeared[object_id]
            })
        return tracks
    
    def draw_tracks(self, frame, tracks, draw_id=True, color=(0, 255, 0)):
        """Dibuja los objetos rastreados en el frame"""
        result_frame = frame.copy()
        
        for track in tracks:
            # Obtener información del track
            bbox = track['bbox']
            track_id = track['id']
            
            # Dibujar bounding box
            cv2.rectangle(
                result_frame,
                (int(bbox[0]), int(bbox[1])),
                (int(bbox[2]), int(bbox[3])),
                color,
                2
            )
            
            # Dibujar ID del objeto
            if draw_id:
                cv2.putText(
                    result_frame,
                    f"ID: {track_id}",
                    (int(bbox[0]), int(bbox[1] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )
                
        return result_frame 