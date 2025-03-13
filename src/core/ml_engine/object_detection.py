from typing import List, Dict, Any, Optional, Tuple
import torch
import numpy as np
from dataclasses import dataclass
from pathlib import Path
import cv2
import random

@dataclass
class Detection:
    """Representa una detección de objeto"""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    class_id: int
    class_name: str
    confidence: float
    frame_id: int

class ObjectDetector:
    def __init__(self, config: Dict[str, Any], test_mode: bool = False):
        self.config = config
        self.device = config.get('device', 'cpu')
        self.confidence_threshold = config.get('confidence_threshold', 0.5)
        self.test_mode = test_mode  # Modo de prueba para no cargar modelo real
        self.classes = self._load_classes()
        
        # Solo cargar el modelo si no estamos en modo de prueba
        if not self.test_mode:
            try:
                self.model = self._load_model()
            except Exception as e:
                # En caso de error, establecer modo de prueba
                print(f"No se pudo cargar el modelo. Usando modo de prueba: {e}")
                self.test_mode = True
        
    def _load_model(self):
        """Carga el modelo de detección"""
        model_path = Path(self.config['model_path'])
        if not model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")
            
        try:
            # Intentar cargar el modelo con force_reload
            model = torch.hub.load(
                'ultralytics/yolov5',
                'custom', 
                path=model_path,
                force_reload=True,
                trust_repo=True  # Añadido para evitar advertencias de seguridad
            )
            return model.to(self.device)
        except Exception as e:
            # Si falla, intentar cargar el modelo directamente
            try:
                model = torch.load(model_path, map_location=self.device)
                if hasattr(model, 'module'):
                    model = model.module
                return model
            except Exception as load_error:
                raise RuntimeError(f"Error al cargar el modelo: {str(e)}\nError secundario: {str(load_error)}")
    
    def _load_classes(self) -> List[str]:
        """Carga las clases desde el archivo"""
        classes_path = Path(self.config.get('classes_path', 'models/coco.names'))
        
        # Clases predeterminadas en caso de que no exista el archivo
        default_classes = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 
            'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
            'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 
            'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 
            'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 
            'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup', 
            'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange', 
            'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 
            'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 
            'toothbrush'
        ]
        
        if not classes_path.exists():
            return default_classes
            
        try:
            with open(classes_path, 'r') as f:
                classes = [line.strip() for line in f.readlines()]
            return classes
        except Exception:
            return default_classes
            
    async def detect(self, frame: np.ndarray, frame_id: int) -> List[Detection]:
        """Detecta objetos en un frame de video"""
        if self.test_mode:
            # En modo de prueba, generar detecciones simuladas
            return self._generate_test_detections(frame, frame_id)
            
        # Preprocesar frame
        img = self._preprocess_frame(frame)
        
        # Realizar inferencia
        with torch.no_grad():
            results = self.model(img)
            
        # Procesar resultados
        detections = []
        
        # Extraer detecciones que superen el umbral de confianza
        for *xyxy, conf, cls in results.xyxy[0]:
            if conf >= self.confidence_threshold:
                x1, y1, x2, y2 = map(int, xyxy)
                class_id = int(cls)
                class_name = self.classes[class_id] if class_id < len(self.classes) else f"class_{class_id}"
                
                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(conf),
                    frame_id=frame_id
                ))
                
        return detections
        
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocesa el frame para la inferencia"""
        return frame  # YOLOv5 no requiere preprocesamiento especial
        
    def _generate_test_detections(self, frame: np.ndarray, frame_id: int) -> List[Detection]:
        """Genera detecciones simuladas para pruebas"""
        height, width = frame.shape[:2]
        detections = []
        
        # Generar 1-3 detecciones aleatorias
        num_detections = random.randint(1, 3)
        
        for _ in range(num_detections):
            # Generar bbox aleatorio
            x1 = random.randint(0, width - 100)
            y1 = random.randint(0, height - 100)
            w = random.randint(50, 200)
            h = random.randint(50, 200)
            x2 = min(x1 + w, width)
            y2 = min(y1 + h, height)
            
            # Clase aleatoria
            class_id = random.randint(0, len(self.classes) - 1)
            class_name = self.classes[class_id]
            
            # Confianza aleatoria por encima del umbral
            confidence = random.uniform(self.confidence_threshold, 1.0)
            
            detections.append(Detection(
                bbox=(x1, y1, x2, y2),
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                frame_id=frame_id
            ))
            
        return detections
        
    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Dibuja las detecciones en el frame"""
        result = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            label = f"{det.class_name} {det.confidence:.2f}"
            
            # Color basado en clase
            color = (
                (det.class_id * 50) % 255,
                (det.class_id * 100) % 255,
                (det.class_id * 150) % 255
            )
            
            # Dibujar bbox
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
            
            # Dibujar etiqueta
            cv2.putText(
                result,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )
            
        return result

__all__ = ['ObjectDetector', 'Detection'] 