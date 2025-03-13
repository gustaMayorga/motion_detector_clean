import torch
import numpy as np
import cv2
from pathlib import Path

class ObjectDetector:
    def __init__(self, model_path="models/yolov5s.pt", confidence=0.5, device=None):
        self.confidence = confidence
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self._load_model(model_path)
        self.classes = self.model.names
        
    def _load_model(self, model_path):
        # Cargar modelo YOLOv5 desde PyTorch Hub o archivo local
        if Path(model_path).exists():
            model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
        else:
            # Usar modelo preentrenado de YOLOv5
            model = torch.hub.load('ultralytics/yolov5', 'yolov5s')
        
        model.to(self.device)
        model.conf = self.confidence  # Umbral de confianza
        return model
        
    def detect(self, frame):
        # Convertir frame a formato adecuado si es necesario
        if isinstance(frame, np.ndarray):
            # Ya es un array numpy
            pass
        elif hasattr(frame, 'numpy'):
            # Convertir a numpy si es un tensor
            frame = frame.numpy()
        
        # Realizar inferencia
        results = self.model(frame)
        
        # Procesar resultados
        detections = []
        for pred in results.xyxy[0]:  # xyxy formato es [x1, y1, x2, y2, conf, class]
            x1, y1, x2, y2, conf, cls = pred.cpu().numpy()
            if conf >= self.confidence:
                detections.append({
                    'class': self.classes[int(cls)],
                    'class_id': int(cls),
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': float(conf)
                })
        
        return detections
    
    def filter_by_class(self, detections, class_names):
        """Filtra las detecciones por nombre de clase"""
        if not class_names:
            return detections
            
        return [d for d in detections if d['class'] in class_names]
    
    def draw_detections(self, frame, detections, color_map=None):
        """Dibuja los bounding boxes en el frame"""
        if color_map is None:
            color_map = {
                'person': (0, 255, 0),     # Verde para personas
                'car': (255, 0, 0),        # Azul para coches
                'truck': (255, 0, 255),    # Magenta para camiones
                'default': (0, 165, 255)   # Naranja por defecto
            }
        
        result_frame = frame.copy()
        
        for det in detections:
            bbox = det['bbox']
            cls = det['class']
            conf = det['confidence']
            
            # Obtener color para la clase o usar el default
            color = color_map.get(cls, color_map['default'])
            
            # Dibujar bounding box
            cv2.rectangle(
                result_frame, 
                (int(bbox[0]), int(bbox[1])), 
                (int(bbox[2]), int(bbox[3])), 
                color, 
                2
            )
            
            # Añadir etiqueta
            label = f"{cls} {conf:.2f}"
            cv2.putText(
                result_frame, 
                label, 
                (int(bbox[0]), int(bbox[1] - 10)), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                color, 
                2
            )
            
        return result_frame 