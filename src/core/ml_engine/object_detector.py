from typing import List, Dict, Any, Tuple
import torch
from pathlib import Path
import numpy as np
from ultralytics import YOLO
import cv2

class ObjectDetector:
    def __init__(self, model_path: str = "yolov8n.pt"):
        """
        Inicializa el detector de objetos
        Args:
            model_path: Ruta al modelo pre-entrenado o personalizado
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self._load_model(model_path)
        self.class_names = self.model.names
        self.confidence_threshold = 0.5
        
    def _load_model(self, model_path: str) -> YOLO:
        """Carga el modelo YOLO"""
        try:
            model = YOLO(model_path)
            model.to(self.device)
            return model
        except Exception as e:
            raise RuntimeError(f"Error cargando modelo: {str(e)}")
            
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detecta objetos en un frame
        Args:
            frame: Imagen en formato numpy array (BGR)
        Returns:
            Lista de detecciones con formato:
            [
                {
                    'bbox': (x1, y1, x2, y2),
                    'class_id': int,
                    'class_name': str,
                    'confidence': float
                },
                ...
            ]
        """
        results = self.model(frame, conf=self.confidence_threshold)[0]
        detections = []
        
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            class_id = int(box.cls)
            confidence = float(box.conf)
            
            detections.append({
                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                'class_id': class_id,
                'class_name': self.class_names[class_id],
                'confidence': confidence
            })
            
        return detections
        
    def draw_detections(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Dibuja las detecciones en el frame
        """
        frame_copy = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            label = f"{det['class_name']} {det['confidence']:.2f}"
            
            # Dibujar bbox
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Dibujar etiqueta
            cv2.putText(
                frame_copy, 
                label, 
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
            
        return frame_copy 