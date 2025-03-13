from typing import Optional, Dict, Any
import cv2
import numpy as np
import pytesseract
from dataclasses import dataclass
import torch
from ultralytics import YOLO

@dataclass
class PlateDetection:
    plate_text: str
    confidence: float
    bbox: tuple
    image: np.ndarray

class PlateRecognizer:
    def __init__(self):
        # Cargar modelo YOLO para detección de placas
        self.plate_detector = YOLO('models/plate_detector.pt')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Configurar Tesseract
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
    async def detect_plate(self, image: np.ndarray) -> Optional[PlateDetection]:
        """Detecta y reconoce una placa en la imagen"""
        try:
            # Detectar región de la placa
            results = self.plate_detector(image)[0]
            if len(results.boxes) == 0:
                return None
                
            # Obtener la detección con mayor confianza
            box = results.boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            
            # Extraer región de la placa
            plate_region = image[y1:y2, x1:x2]
            
            # Preprocesar imagen
            processed_plate = self._preprocess_plate(plate_region)
            
            # OCR en la región de la placa
            plate_text = pytesseract.image_to_string(
                processed_plate,
                config=self.tesseract_config
            ).strip()
            
            if not plate_text:
                return None
                
            return PlateDetection(
                plate_text=plate_text,
                confidence=confidence,
                bbox=(x1, y1, x2, y2),
                image=processed_plate
            )
            
        except Exception as e:
            print(f"Error en reconocimiento de placa: {e}")
            return None
            
    def _preprocess_plate(self, plate_img: np.ndarray) -> np.ndarray:
        """Preprocesa la imagen de la placa para mejorar OCR"""
        # Convertir a escala de grises
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        
        # Aplicar umbral adaptativo
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Reducir ruido
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        # Dilatar para conectar componentes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        dilated = cv2.dilate(denoised, kernel, iterations=1)
        
        return dilated 