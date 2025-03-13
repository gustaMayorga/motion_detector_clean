import os
import cv2
import numpy as np
import logging
import time
import pickle
import threading
import json
from datetime import datetime
import uuid
from pathlib import Path
import tensorflow as tf
from sklearn.preprocessing import Normalizer
from sklearn.neighbors import NearestNeighbors

class FaceRecognitionSystem:
    """
    Sistema de reconocimiento facial para identificación de personas
    
    Detecta, extrae características y compara rostros con una base de datos
    de personas conocidas para identificación en tiempo real.
    """
    
    def __init__(self, config=None):
        """
        Inicializar sistema de reconocimiento facial
        
        Args:
            config: Configuración del sistema con parámetros como:
                - model_path: Ruta al modelo de detección/reconocimiento
                - face_db_path: Ruta a la base de datos de rostros conocidos
                - detection_threshold: Umbral para detección (0-1)
                - recognition_threshold: Umbral para reconocimiento (0-1)
                - min_face_size: Tamaño mínimo de rostro en píxeles
                - use_gpu: Usar aceleración GPU si está disponible
        """
        self.logger = logging.getLogger('FaceRecognitionSystem')
        self.config = config or {}
        
        # Directorio para modelos
        self.models_dir = self.config.get('models_dir', 'models/face')
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Parámetros de detección y reconocimiento
        self.detection_threshold = self.config.get('detection_threshold', 0.7)
        self.recognition_threshold = self.config.get('recognition_threshold', 0.6)
        self.min_face_size = self.config.get('min_face_size', 80)
        
        # Base de datos de rostros
        self.face_db_path = self.config.get('face_db_path', 'data/faces')
        os.makedirs(self.face_db_path, exist_ok=True)
        
        # Cargar base de datos de rostros
        self.face_database = {}
        self.face_embeddings = []
        self.face_identities = []
        self.knn_model = None
        
        # Mutex para acceso a BD de rostros
        self.db_lock = threading.Lock()
        
        # Inicializar modelos
        self.detector = None
        self.recognizer = None
        self._load_models()
        
        # Cargar base de datos de rostros
        self._load_face_database()
        
        self.logger.info("Sistema de reconocimiento facial inicializado")
    
    def _load_models(self):
        """Cargar modelos de detección y reconocimiento facial"""
        try:
            # Cargar modelo de detección facial
            detector_path = self.config.get('detector_model_path')
            if not detector_path:
                detector_path = os.path.join(self.models_dir, 'face_detection_model')
                
            if not os.path.exists(detector_path):
                self.logger.warning(f"Modelo de detección no encontrado en {detector_path}")
                self._download_detection_model(detector_path)
                
            self.detector = cv2.FaceDetectorYN.create(
                detector_path,
                "",
                (320, 320),
                self.detection_threshold,
                0,
                self.config.get('nms_threshold', 0.3)
            )
            
            # Cargar modelo de embeddings faciales
            recognizer_path = self.config.get('recognizer_model_path')
            if not recognizer_path:
                recognizer_path = os.path.join(self.models_dir, 'face_recognition_model')
                
            if not os.path.exists(recognizer_path):
                self.logger.warning(f"Modelo de reconocimiento no encontrado en {recognizer_path}")
                self._download_recognition_model(recognizer_path)
            
            # Cargar modelo para extracción de embeddings
            self.recognizer = tf.saved_model.load(recognizer_path)
            
            self.logger.info("Modelos de detección y reconocimiento facial cargados")
            
        except Exception as e:
            self.logger.error(f"Error al cargar modelos de reconocimiento facial: {e}")
            raise
            
    def _download_detection_model(self, target_path):
        """Descargar modelo de detección facial pre-entrenado"""
        try:
            # URL para YuNet (modelo ligero de OpenCV)
            url = "https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            import urllib.request
            self.logger.info(f"Descargando modelo de detección facial desde {url}")
            urllib.request.urlretrieve(url, target_path)
            
            self.logger.info(f"Modelo de detección facial descargado en {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error al descargar modelo de detección facial: {e}")
            return False
            
    def _download_recognition_model(self, target_path):
        """Descargar modelo de reconocimiento facial pre-entrenado"""
        try:
            # En una aplicación real, descargaríamos el modelo desde un repositorio seguro
            # Para este ejemplo, informamos que no se puede descargar automáticamente
            self.logger.error(f"El modelo de reconocimiento facial debe ser instalado manualmente en {target_path}")
            
            # Instrucciones para el usuario
            print(f"""
            ====== ATENCIÓN: MODELO DE RECONOCIMIENTO FACIAL REQUERIDO ======
            
            Por favor, descargue el modelo de reconocimiento facial y colóquelo en:
            {target_path}
            
            Opciones recomendadas:
            1. FaceNet: https://github.com/davidsandberg/facenet
            2. ArcFace: https://github.com/deepinsight/insightface
            3. DeepFace: https://github.com/serengil/deepface
            
            Luego reinicie el sistema.
            ==============================================================
            """)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error en descarga de modelo de reconocimiento: {e}")
            return False
    
    def _load_face_database(self):
        """Cargar base de datos de rostros conocidos"""
        try:
            with self.db_lock:
                db_file = os.path.join(self.face_db_path, 'face_database.pkl')
                embeddings_file = os.path.join(self.face_db_path, 'face_embeddings.pkl')
                
                # Cargar metadatos de personas
                if os.path.exists(db_file):
                    with open(db_file, 'rb') as f:
                        self.face_database = pickle.load(f)
                    self.logger.info(f"Base de datos de rostros cargada: {len(self.face_database)} personas")
                
                # Cargar embeddings para búsqueda rápida
                if os.path.exists(embeddings_file):
                    with open(embeddings_file, 'rb') as f:
                        data = pickle.load(f)
                        self.face_embeddings = data.get('embeddings', [])
                        self.face_identities = data.get('identities', [])
                    
                    # Inicializar KNN para búsqueda eficiente
                    if len(self.face_embeddings) > 0:
                        self._init_knn_model()
                        
                    self.logger.info(f"Embeddings faciales cargados: {len(self.face_embeddings)} rostros")
                
        except Exception as e:
            self.logger.error(f"Error al cargar base de datos de rostros: {e}")
            
    def _init_knn_model(self):
        """Inicializar modelo KNN para búsqueda eficiente de rostros similares"""
        try:
            if len(self.face_embeddings) > 0:
                X = np.array(self.face_embeddings)
                self.knn_model = NearestNeighbors(n_neighbors=min(5, len(X)), 
                                                 algorithm='auto', 
                                                 metric='euclidean')
                self.knn_model.fit(X)
                self.logger.info("Modelo KNN inicializado para búsqueda de rostros")
            else:
                self.knn_model = None
                
        except Exception as e:
            self.logger.error(f"Error al inicializar modelo KNN: {e}")
            self.knn_model = None
    
    def _save_face_database(self):
        """Guardar base de datos de rostros"""
        try:
            with self.db_lock:
                db_file = os.path.join(self.face_db_path, 'face_database.pkl')
                embeddings_file = os.path.join(self.face_db_path, 'face_embeddings.pkl')
                
                # Guardar metadatos de personas
                with open(db_file, 'wb') as f:
                    pickle.dump(self.face_database, f)
                
                # Guardar embeddings para búsqueda rápida
                with open(embeddings_file, 'wb') as f:
                    data = {
                        'embeddings': self.face_embeddings,
                        'identities': self.face_identities
                    }
                    pickle.dump(data, f)
                    
                self.logger.info(f"Base de datos de rostros guardada: {len(self.face_database)} personas")
                return True
                
        except Exception as e:
            self.logger.error(f"Error al guardar base de datos de rostros: {e}")
            return False
    
    def detect_faces(self, frame):
        """
        Detectar rostros en un frame
        
        Args:
            frame: Imagen de entrada (array de OpenCV)
            
        Returns:
            Lista de rostros detectados con sus coordenadas
        """
        if self.detector is None:
            self.logger.error("Detector facial no inicializado")
            return []
            
        try:
            # Preparar imagen para detección
            height, width, _ = frame.shape
            self.detector.setInputSize((width, height))
            
            # Detectar rostros
            faces, landmarks = self.detector.detect(frame)
            
            if faces is None:
                return []
                
            # Preparar resultados
            detections = []
            for i, face in enumerate(faces):
                x, y, w, h, confidence = face
                
                if confidence < self.detection_threshold:
                    continue
                    
                if w < self.min_face_size or h < self.min_face_size:
                    continue
                
                # Convertir a enteros
                x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)
                
                # Guardar landmarks si están disponibles
                face_landmarks = None
                if landmarks is not None and i < len(landmarks):
                    face_landmarks = landmarks[i]
                
                # Añadir a resultados
                detections.append({
                    'bbox': (x1, y1, x2, y2),
                    'confidence': float(confidence),
                    'landmarks': face_landmarks
                })
                
            return detections
            
        except Exception as e:
            self.logger.error(f"Error en detección facial: {e}")
            return []
    
    def extract_face_embedding(self, frame, face_detection):
        """
        Extraer características faciales (embedding)
        
        Args:
            frame: Imagen de entrada
            face_detection: Diccionario con datos de detección (bbox, etc.)
            
        Returns:
            Vector de embedding facial (características)
        """
        if self.recognizer is None:
            self.logger.error("Modelo de reconocimiento no inicializado")
            return None
            
        try:
            # Obtener coordenadas del rostro
            x1, y1, x2, y2 = face_detection['bbox']
            
            # Extraer rostro y preprocesar
            face_img = frame[y1:y2, x1:x2]
            
            # Redimensionar a tamaño esperado por el modelo
            face_img = cv2.resize(face_img, (160, 160))
            
            # Normalizar imagen para el modelo
            face_img = face_img.astype(np.float32) / 255.0
            face_img = np.expand_dims(face_img, axis=0)  # Añadir dimensión de batch
            
            # Extraer embedding usando el modelo
            embedding = self.recognizer(face_img)
            
            # Normalizar embedding
            l2_normalizer = Normalizer('l2')
            embedding = l2_normalizer.transform(embedding.numpy())
            
            return embedding[0]  # Retornar solo el primer embedding
            
        except Exception as e:
            self.logger.error(f"Error al extraer embedding facial: {e}")
            return None
    
    def identify_face(self, embedding):
        """
        Identificar rostro a partir de su embedding
        
        Args:
            embedding: Vector de características del rostro
            
        Returns:
            Información de la persona identificada o None si es desconocida
        """
        if self.knn_model is None or len(self.face_identities) == 0:
            return None
            
        try:
            # Buscar rostros similares con KNN
            distances, indices = self.knn_model.kneighbors([embedding])
            
            # Verificar si la distancia es menor al umbral de reconocimiento
            if distances[0][0] > self.recognition_threshold:
                return None  # Rostro desconocido
                
            # Obtener ID de la persona más similar
            person_id = self.face_identities[indices[0][0]]
            
            # Obtener información completa de la persona
            person_info = self.face_database.get(person_id, None)
            if person_info:
                # Añadir distancia (confianza) al resultado
                result = person_info.copy()
                result['distance'] = float(distances[0][0])
                result['confidence'] = 1.0 - float(distances[0][0])
                return result
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error al identificar rostro: {e}")
            return None
    
    def process_frame(self, frame):
        """
        Procesar frame para detectar y reconocer rostros
        
        Args:
            frame: Imagen de entrada (array de OpenCV)
            
        Returns:
            Lista de rostros detectados con identidades asociadas
        """
        # Detectar rostros
        face_detections = self.detect_faces(frame)
        
        # Procesar cada rostro detectado
        processed_faces = []
        for face in face_detections:
            # Extraer embedding
            embedding = self.extract_face_embedding(frame, face)
            
            if embedding is None:
                continue
                
            # Buscar identidad
            identity = self.identify_face(embedding)
            
            # Preparar resultado
            result = {
                'detection': face,
                'bbox': face['bbox'],
                'embedding': embedding.tolist(),
                'identity': identity,
                'is_known': identity is not None
            }
            
            processed_faces.append(result)
            
        return processed_faces
    
    def register_new_face(self, frame, face_detection, person_info):
        """
        Registrar nuevo rostro en la base de datos
        
        Args:
            frame: Imagen que contiene el rostro
            face_detection: Detección del rostro a registrar
            person_info: Diccionario con información de la persona (nombre, etc.)
            
        Returns:
            ID de la persona registrada o None si falla
        """
        try:
            # Extraer embedding del rostro
            embedding = self.extract_face_embedding(frame, face_detection)
            
            if embedding is None:
                self.logger.error("No se pudo extraer embedding del rostro")
                return None
                
            # Generar ID único para la persona si no se proporcionó
            person_id = person_info.get('id', str(uuid.uuid4()))
            
            # Complementar información de la persona
            full_info = person_info.copy()
            full_info['id'] = person_id
            
            if 'registration_time' not in full_info:
                full_info['registration_time'] = datetime.now().isoformat()
                
            # Guardar imagen del rostro
            self._save_face_image(frame, face_detection, person_id)
            
            # Actualizar base de datos
            with self.db_lock:
                # Añadir a la base de datos
                self.face_database[person_id] = full_info
                
                # Añadir embedding a la lista
                self.face_embeddings.append(embedding)
                self.face_identities.append(person_id)
                
                # Reinicializar KNN
                self._init_knn_model()
                
                # Guardar base de datos
                self._save_face_database()
                
            self.logger.info(f"Rostro registrado para persona {person_id}")
            return person_id
            
        except Exception as e:
            self.logger.error(f"Error al registrar nuevo rostro: {e}")
            return None
    
    def _save_face_image(self, frame, face_detection, person_id):
        """Guardar imagen recortada del rostro"""
        try:
            # Crear directorio para imágenes de rostros
            person_dir = os.path.join(self.face_db_path, 'images', person_id)
            os.makedirs(person_dir, exist_ok=True)
            
            # Recortar rostro
            x1, y1, x2, y2 = face_detection['bbox']
            face_img = frame[y1:y2, x1:x2]
            
            # Generar nombre de archivo único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{person_id}_{timestamp}.jpg"
            filepath = os.path.join(person_dir, filename)
            
            # Guardar imagen
            cv2.imwrite(filepath, face_img)
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error al guardar imagen del rostro: {e}")
            return None
    
    def delete_person(self, person_id):
        """
        Eliminar persona de la base de datos
        
        Args:
            person_id: ID de la persona a eliminar
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            with self.db_lock:
                # Verificar si la persona existe
                if person_id not in self.face_database:
                    self.logger.warning(f"Persona {person_id} no encontrada en la base de datos")
                    return False
                    
                # Eliminar de la base de datos
                del self.face_database[person_id]
                
                # Eliminar embeddings asociados
                indices_to_remove = []
                for i, identity in enumerate(self.face_identities):
                    if identity == person_id:
                        indices_to_remove.append(i)
                
                # Eliminar desde el final para evitar cambios en índices
                for i in sorted(indices_to_remove, reverse=True):
                    del self.face_embeddings[i]
                    del self.face_identities[i]
                
                # Reinicializar KNN si hay embeddings
                self._init_knn_model()
                
                # Guardar cambios
                self._save_face_database()
                
                # Intentar eliminar directorio de imágenes
                person_dir = os.path.join(self.face_db_path, 'images', person_id)
                if os.path.exists(person_dir):
                    import shutil
                    shutil.rmtree(person_dir)
                
                self.logger.info(f"Persona {person_id} eliminada de la base de datos")
                return True
                
        except Exception as e:
            self.logger.error(f"Error al eliminar persona {person_id}: {e}")
            return False
    
    def get_all_persons(self):
        """
        Obtener lista de todas las personas registradas
        
        Returns:
            Lista de diccionarios con información de las personas
        """
        try:
            with self.db_lock:
                return list(self.face_database.values())
                
        except Exception as e:
            self.logger.error(f"Error al obtener lista de personas: {e}")
            return []
    
    def get_person(self, person_id):
        """
        Obtener información de una persona específica
        
        Args:
            person_id: ID de la persona
            
        Returns:
            Diccionario con información de la persona o None si no existe
        """
        try:
            with self.db_lock:
                return self.face_database.get(person_id, None)
                
        except Exception as e:
            self.logger.error(f"Error al obtener información de persona {person_id}: {e}")
            return None
    
    def update_person_info(self, person_id, updated_info):
        """
        Actualizar información de una persona
        
        Args:
            person_id: ID de la persona
            updated_info: Diccionario con información actualizada
            
        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            with self.db_lock:
                # Verificar si la persona existe
                if person_id not in self.face_database:
                    self.logger.warning(f"Persona {person_id} no encontrada")
                    return False
                    
                # Obtener información actual
                current_info = self.face_database[person_id]
                
                # Actualizar campos (sin cambiar id ni tiempo de registro)
                for key, value in updated_info.items():
                    if key not in ['id', 'registration_time']:
                        current_info[key] = value
                
                # Guardar cambios
                self._save_face_database()
                
                self.logger.info(f"Información de persona {person_id} actualizada")
                return True
                
        except Exception as e:
            self.logger.error(f"Error al actualizar información de persona {person_id}: {e}")
            return False
    
    def annotate_frame(self, frame, processed_faces, include_unknown=True):
        """
        Anotar frame con rostros detectados e identidades
        
        Args:
            frame: Imagen de entrada
            processed_faces: Lista de rostros procesados con identidades
            include_unknown: Incluir rostros desconocidos en la anotación
            
        Returns:
            Imagen anotada con cuadros y nombres
        """
        try:
            # Crear copia de la imagen para no modificar la original
            vis_image = frame.copy()
            
            # Colores para mostrar (BGR)
            known_color = (0, 255, 0)  # Verde para personas conocidas
            unknown_color = (0, 0, 255)  # Rojo para personas desconocidas
            
            # Anotar cada rostro
            for face in processed_faces:
                # Obtener coordenadas
                x1, y1, x2, y2 = face['bbox']
                
                # Verificar si es persona conocida
                identity = face.get('identity')
                is_known = identity is not None
                
                # Si no incluimos desconocidos y esta persona es desconocida, saltamos
                if not include_unknown and not is_known:
                    continue
                    
                # Seleccionar color
                color = known_color if is_known else unknown_color
                
                # Dibujar rectángulo
                cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
                
                # Preparar texto
                if is_known:
                    name = identity.get('name', 'Sin nombre')
                    confidence = identity.get('confidence', 0) * 100
                    text = f"{name} ({confidence:.1f}%)"
                else:
                    text = "Desconocido"
                    
                # Fondo para el texto
                text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(vis_image, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), color, -1)
                
                # Dibujar texto
                cv2.putText(vis_image, text, (x1, y1 - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                          
            return vis_image
            
        except Exception as e:
            self.logger.error(f"Error al anotar frame: {e}")
            return frame 