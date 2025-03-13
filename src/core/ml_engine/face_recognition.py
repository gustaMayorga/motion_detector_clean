from typing import List, Dict, Any, Optional
import numpy as np
import cv2
import torch
from pathlib import Path
import face_recognition
import asyncio
from datetime import datetime
import json

class FaceRecognizer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.known_faces: Dict[str, np.ndarray] = {}
        self.known_names: Dict[str, str] = {}
        self._load_known_faces()
        
        self.detection_lock = asyncio.Lock()
        self.batch_size = config.get('batch_size', 4)
        self.min_face_size = config.get('min_face_size', 20)
        
    def _load_known_faces(self):
        """Carga las caras conocidas desde el directorio de entrenamiento"""
        faces_dir = Path(self.config['faces_dir'])
        if not faces_dir.exists():
            raise RuntimeError(f"Directorio de caras no encontrado: {faces_dir}")
            
        for user_dir in faces_dir.iterdir():
            if not user_dir.is_dir():
                continue
                
            user_id = user_dir.name
            encodings = []
            
            for img_path in user_dir.glob("*.jpg"):
                try:
                    image = face_recognition.load_image_file(str(img_path))
                    encoding = face_recognition.face_encodings(image)[0]
                    encodings.append(encoding)
                except Exception as e:
                    print(f"Error cargando imagen {img_path}: {e}")
                    continue
                    
            if encodings:
                self.known_faces[user_id] = np.mean(encodings, axis=0)
                
                # Cargar nombre del usuario
                meta_file = user_dir / "metadata.json"
                if meta_file.exists():
                    with open(meta_file) as f:
                        metadata = json.load(f)
                        self.known_names[user_id] = metadata.get('name', user_id)
                        
    async def identify_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Identifica rostros en un frame"""
        async with self.detection_lock:
            # Detectar rostros
            face_locations = face_recognition.face_locations(
                frame,
                model="cnn" if torch.cuda.is_available() else "hog"
            )
            
            if not face_locations:
                return []
                
            # Obtener encodings
            face_encodings = face_recognition.face_encodings(frame, face_locations)
            
            results = []
            for location, encoding in zip(face_locations, face_encodings):
                matches = face_recognition.compare_faces(
                    list(self.known_faces.values()),
                    encoding,
                    tolerance=self.config.get('similarity_threshold', 0.6)
                )
                
                if True in matches:
                    # Encontrar la mejor coincidencia
                    face_distances = face_recognition.face_distance(
                        list(self.known_faces.values()),
                        encoding
                    )
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        user_id = list(self.known_faces.keys())[best_match_index]
                        confidence = 1 - face_distances[best_match_index]
                        
                        results.append({
                            'user_id': user_id,
                            'name': self.known_names.get(user_id, user_id),
                            'confidence': float(confidence),
                            'location': location,
                            'timestamp': datetime.now()
                        })
                        
            return results
            
    async def add_face(self, user_id: str, image: np.ndarray) -> bool:
        """Añade una nueva cara al conjunto de entrenamiento"""
        try:
            face_locations = face_recognition.face_locations(image)
            if not face_locations:
                return False
                
            encoding = face_recognition.face_encodings(image, face_locations)[0]
            
            if user_id in self.known_faces:
                # Actualizar encoding existente
                current_encoding = self.known_faces[user_id]
                self.known_faces[user_id] = np.mean(
                    [current_encoding, encoding],
                    axis=0
                )
            else:
                self.known_faces[user_id] = encoding
                
            # Guardar imagen
            faces_dir = Path(self.config['faces_dir']) / user_id
            faces_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(
                str(faces_dir / f"{timestamp}.jpg"),
                cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            )
            
            return True
            
        except Exception as e:
            print(f"Error añadiendo cara: {e}")
            return False 