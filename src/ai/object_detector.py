import cv2
import numpy as np
import logging
import time
import os
from threading import Thread, Lock
import tensorflow as tf

class ObjectDetector:
    """
    Detector de objetos basado en modelos pre-entrenados.
    Soporta diferentes backends: TensorFlow, OpenCV DNN, YOLOv5
    """
    
    def __init__(self, config=None):
        """
        Inicializar detector con configuración especificada
        
        Args:
            config: Diccionario de configuración con los siguientes campos:
                - model_type: 'tensorflow', 'opencv_dnn', 'yolov5'
                - model_path: Ruta al modelo
                - confidence_threshold: Umbral de confianza (0-1)
                - classes_of_interest: Lista de clases a detectar
                - device: 'cpu' o 'gpu'
        """
        self.logger = logging.getLogger('ObjectDetector')
        
        # Configuración por defecto
        default_config = {
            'model_type': 'tensorflow',
            'model_path': 'models/ssd_mobilenet_v2_coco',
            'confidence_threshold': 0.5,
            'classes_of_interest': ['person', 'car', 'truck', 'bicycle', 'motorcycle', 'bus'],
            'device': 'cpu',
            'max_batch_size': 4
        }
        
        # Aplicar configuración
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        self.model = None
        self.running = False
        self.detection_queue = []
        self.queue_lock = Lock()
        self.processing_thread = None
        self.class_names = []
        
        # Inicializar modelo
        self._load_model()
        
    def _load_model(self):
        """Cargar el modelo de detección según la configuración"""
        try:
            model_type = self.config['model_type']
            
            self.logger.info(f"Cargando modelo de detección tipo: {model_type}")
            
            if model_type == 'tensorflow':
                self._load_tensorflow_model()
            elif model_type == 'opencv_dnn':
                self._load_opencv_dnn_model()
            elif model_type == 'yolov5':
                self._load_yolov5_model()
            else:
                raise ValueError(f"Tipo de modelo no soportado: {model_type}")
                
            self.logger.info("Modelo de detección cargado correctamente")
            
        except Exception as e:
            self.logger.error(f"Error al cargar modelo de detección: {e}")
            raise
            
    def _load_tensorflow_model(self):
        """Cargar modelo TensorFlow/TF-Lite"""
        model_path = self.config['model_path']
        
        # Configurar dispositivo
        if self.config['device'] == 'gpu':
            # Permitir crecimiento de memoria GPU según necesidad
            physical_devices = tf.config.list_physical_devices('GPU')
            if physical_devices:
                tf.config.experimental.set_memory_growth(physical_devices[0], True)
        else:
            # Forzar CPU
            os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
            
        # Cargar modelo según extensión
        if model_path.endswith('.tflite'):
            # Modelo TF-Lite
            self.interpreter = tf.lite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            
            # Obtener detalles del modelo
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Dimensiones de entrada esperadas
            self.input_shape = self.input_details[0]['shape']
            
            # Cargar nombres de clases
            labels_path = os.path.join(os.path.dirname(model_path), 'labelmap.txt')
            if os.path.exists(labels_path):
                with open(labels_path, 'r') as f:
                    self.class_names = [line.strip() for line in f.readlines()]
            
        else:
            # Modelo SavedModel
            self.model = tf.saved_model.load(model_path)
            self.detect_fn = self.model.signatures['serving_default']
            
            # Cargar nombres de clases
            labels_path = os.path.join(model_path, 'label_map.pbtxt')
            if os.path.exists(labels_path):
                self.class_names = self._parse_labelmap(labels_path)
                
    def _parse_labelmap(self, labelmap_path):
        """Parsear archivo de mapeo de etiquetas de TensorFlow"""
        class_names = {}
        with open(labelmap_path, 'r') as f:
            content = f.read()
            
        for item in content.split('item {')[1:]:
            id_match = re.search(r'id: (\d+)', item)
            name_match = re.search(r'display_name: [\'"](.+?)[\'"]', item)
            if not name_match:
                name_match = re.search(r'name: [\'"](.+?)[\'"]', item)
                
            if id_match and name_match:
                class_id = int(id_match.group(1))
                class_name = name_match.group(1)
                class_names[class_id] = class_name
                
        return [class_names.get(i, f"class_{i}") for i in range(1, max(class_names.keys()) + 1)]
    
    def _load_opencv_dnn_model(self):
        """Cargar modelo usando OpenCV DNN"""
        model_path = self.config['model_path']
        config_path = self.config.get('config_path', 
                                      os.path.join(os.path.dirname(model_path), 'config.pbtxt'))
        
        # Cargar modelo
        self.model = cv2.dnn.readNetFromTensorflow(model_path, config_path)
        
        # Configurar dispositivo
        if self.config['device'] == 'gpu':
            self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        else:
            self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            
        # Cargar nombres de clases
        labels_path = self.config.get('labels_path', 
                                      os.path.join(os.path.dirname(model_path), 'labels.txt'))
        if os.path.exists(labels_path):
            with open(labels_path, 'r') as f:
                self.class_names = [line.strip() for line in f.readlines()]
                
    def _load_yolov5_model(self):
        """Cargar modelo YOLOv5 usando PyTorch"""
        try:
            import torch
            
            model_path = self.config['model_path']
            
            # Cargar modelo desde archivo o hub
            if os.path.exists(model_path):
                self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
            else:
                # Cargar desde hub (e.g., 'yolov5s', 'yolov5m', etc.)
                self.model = torch.hub.load('ultralytics/yolov5', model_path)
                
            # Configurar dispositivo
            device = 'cuda' if self.config['device'] == 'gpu' and torch.cuda.is_available() else 'cpu'
            self.model.to(device)
            
            # Configurar umbral de confianza
            self.model.conf = self.config['confidence_threshold']
            
            # Las clases están incluidas en el modelo YOLOv5
            self.class_names = self.model.names
            
        except ImportError:
            self.logger.error("No se pudo cargar PyTorch. Instale con: pip install torch")
            raise
            
    def start_detection_thread(self):
        """Iniciar hilo de procesamiento para detección en segundo plano"""
        if self.processing_thread is not None and self.processing_thread.is_alive():
            self.logger.warning("El hilo de detección ya está en ejecución")
            return
            
        self.running = True
        self.processing_thread = Thread(target=self._detection_worker, daemon=True)
        self.processing_thread.start()
        self.logger.info("Hilo de detección iniciado")
        
    def stop_detection_thread(self):
        """Detener hilo de procesamiento de detección"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
            if self.processing_thread.is_alive():
                self.logger.warning("El hilo de detección no se detuvo correctamente")
                
        self.logger.info("Hilo de detección detenido")
        
    def _detection_worker(self):
        """Función de trabajo para el hilo de detección"""
        while self.running:
            # Procesar cola en lotes para mejorar eficiencia
            batch = []
            callbacks = []
            
            with self.queue_lock:
                # Obtener hasta max_batch_size imágenes de la cola
                batch_size = min(len(self.detection_queue), self.config['max_batch_size'])
                if batch_size > 0:
                    batch_items = self.detection_queue[:batch_size]
                    self.detection_queue = self.detection_queue[batch_size:]
                    
                    for item in batch_items:
                        batch.append(item[0])  # Imagen
                        callbacks.append(item[1])  # Callback
            
            # Procesar lote si no está vacío
            if batch:
                try:
                    # Detectar objetos en todas las imágenes
                    results = self.detect_batch(batch)
                    
                    # Llamar a los callbacks con los resultados
                    for i, (result, callback) in enumerate(zip(results, callbacks)):
                        if callback:
                            try:
                                callback(result)
                            except Exception as e:
                                self.logger.error(f"Error en callback de detección #{i}: {e}")
                                
                except Exception as e:
                    self.logger.error(f"Error procesando lote de detección: {e}")
                    # Informar error a los callbacks
                    for callback in callbacks:
                        if callback:
                            try:
                                callback(None)  # Indicar error con None
                            except Exception as cb_err:
                                pass
            else:
                # Si no hay nada que procesar, dormir para reducir uso de CPU
                time.sleep(0.01)
                
    def detect_async(self, image, callback=None):
        """
        Solicitar detección asíncrona de objetos
        
        Args:
            image: Imagen numpy (BGR) o ruta a imagen
            callback: Función a llamar con los resultados
        """
        # Cargar imagen si es una ruta
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"No se pudo cargar la imagen: {image}")
                
        # Encolar solicitud
        with self.queue_lock:
            self.detection_queue.append((image, callback))
            
        # Iniciar hilo de procesamiento si no está corriendo
        if not self.running or self.processing_thread is None or not self.processing_thread.is_alive():
            self.start_detection_thread()
            
    def detect(self, image):
        """
        Detectar objetos en una imagen (síncrono)
        
        Args:
            image: Imagen numpy (BGR) o ruta a imagen
            
        Returns:
            Lista de detecciones, cada una con:
            {
                'class_id': ID de clase,
                'class_name': Nombre de la clase,
                'confidence': Confianza (0-1),
                'bbox': [x1, y1, x2, y2] en píxeles
            }
        """
        # Cargar imagen si es una ruta
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"No se pudo cargar la imagen: {image}")
                
        return self.detect_batch([image])[0]
        
    def detect_batch(self, images):
        """
        Detectar objetos en un lote de imágenes
        
        Args:
            images: Lista de imágenes numpy (BGR)
            
        Returns:
            Lista de resultados, uno por imagen
        """
        if not images:
            return []
            
        model_type = self.config['model_type']
        
        if model_type == 'tensorflow':
            return self._detect_tensorflow_batch(images)
        elif model_type == 'opencv_dnn':
            return [self._detect_opencv_dnn(img) for img in images]
        elif model_type == 'yolov5':
            return self._detect_yolov5_batch(images)
        else:
            raise ValueError(f"Tipo de modelo no soportado: {model_type}")
            
    def _detect_tensorflow_batch(self, images):
        """Detección con TensorFlow"""
        results = []
        
        # Verificar si es modelo TFLite
        if hasattr(self, 'interpreter'):
            # Procesamiento individual para TFLite
            for image in images:
                results.append(self._detect_tflite(image))
        else:
            # Procesamiento por lotes para SavedModel
            batch_tensor = tf.convert_to_tensor(
                [self._preprocess_tf_image(img) for img in images]
            )
            
            detections = self.detect_fn(batch_tensor)
            
            # Procesar cada imagen en el lote
            for i, image in enumerate(images):
                height, width = image.shape[:2]
                
                # Extraer resultados para esta imagen
                boxes = detections['detection_boxes'][i].numpy()
                scores = detections['detection_scores'][i].numpy()
                classes = detections['detection_classes'][i].numpy().astype(np.int32)
                
                # Filtrar por umbral de confianza
                threshold = self.config['confidence_threshold']
                mask = scores >= threshold
                
                filtered_boxes = boxes[mask]
                filtered_scores = scores[mask]
                filtered_classes = classes[mask]
                
                # Convertir a formato común
                detections_list = []
                
                for j in range(len(filtered_scores)):
                    # Convertir coordenadas relativas [0,1] a píxeles
                    y1, x1, y2, x2 = filtered_boxes[j]
                    x1, y1, x2, y2 = int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
                    
                    class_id = filtered_classes[j]
                    class_name = self.class_names[class_id - 1] if class_id <= len(self.class_names) else f"class_{class_id}"
                    
                    # Filtrar por clases de interés
                    if class_name in self.config['classes_of_interest'] or not self.config['classes_of_interest']:
                        detections_list.append({
                            'class_id': int(class_id),
                            'class_name': class_name,
                            'confidence': float(filtered_scores[j]),
                            'bbox': [x1, y1, x2, y2]
                        })
                
                results.append(detections_list)
                
        return results
        
    def _detect_tflite(self, image):
        """Detección con TF-Lite"""
        # Redimensionar imagen según el modelo
        height, width = image.shape[:2]
        input_h, input_w = self.input_shape[1], self.input_shape[2]
        
        resized = cv2.resize(image, (input_w, input_h))
        resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalizar y preparar input
        input_data = np.expand_dims(resized_rgb, axis=0)
        if input_data.dtype != np.float32:
            input_data = input_data.astype(np.float32) / 255.0
            
        # Ejecutar inferencia
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        
        # Obtener resultados
        boxes = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        classes = self.interpreter.get_tensor(self.output_details[1]['index'])[0]
        scores = self.interpreter.get_tensor(self.output_details[2]['index'])[0]
        
        # Filtrar por umbral de confianza
        threshold = self.config['confidence_threshold']
        mask = scores >= threshold
        
        filtered_boxes = boxes[mask]
        filtered_scores = scores[mask]
        filtered_classes = classes[mask].astype(np.int32)
        
        # Convertir a formato común
        detections_list = []
        
        for i in range(len(filtered_scores)):
            # Convertir coordenadas relativas [0,1] a píxeles
            y1, x1, y2, x2 = filtered_boxes[i]
            x1, y1, x2, y2 = int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
            
            class_id = filtered_classes[i]
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"
            
            # Filtrar por clases de interés
            if class_name in self.config['classes_of_interest'] or not self.config['classes_of_interest']:
                detections_list.append({
                    'class_id': int(class_id),
                    'class_name': class_name,
                    'confidence': float(filtered_scores[i]),
                    'bbox': [x1, y1, x2, y2]
                })
        
        return detections_list
        
    def _preprocess_tf_image(self, image):
        """Preprocesar imagen para TensorFlow"""
        # Convertir BGR a RGB (TensorFlow espera RGB)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Mantener los valores como están - el modelo se encarga de la normalización
        return rgb_image
        
    def _detect_opencv_dnn(self, image):
        """Detección con OpenCV DNN"""
        height, width = image.shape[:2]
        
        # Preparar blob de entrada
        blob = cv2.dnn.blobFromImage(image, size=(300, 300), swapRB=True, crop=False)
        
        # Ejecutar inferencia
        self.model.setInput(blob)
        detections = self.model.forward()
        
        # Procesar resultados
        results = []
        
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            # Filtrar por umbral de confianza
            if confidence < self.config['confidence_threshold']:
                continue
                
            # Extraer índice de clase
            class_id = int(detections[0, 0, i, 1])
            
            # Obtener nombre de clase
            if 0 <= class_id < len(self.class_names):
                class_name = self.class_names[class_id]
            else:
                class_name = f"class_{class_id}"
                
            # Filtrar por clases de interés
            if class_name not in self.config['classes_of_interest'] and self.config['classes_of_interest']:
                continue
                
            # Extraer coordenadas de la caja
            x1 = int(detections[0, 0, i, 3] * width)
            y1 = int(detections[0, 0, i, 4] * height)
            x2 = int(detections[0, 0, i, 5] * width)
            y2 = int(detections[0, 0, i, 6] * height)
            
            # Agregar a resultados
            results.append({
                'class_id': class_id,
                'class_name': class_name,
                'confidence': float(confidence),
                'bbox': [x1, y1, x2, y2]
            })
            
        return results
        
    def _detect_yolov5_batch(self, images):
        """Detección con YOLOv5"""
        # YOLOv5 espera RGB
        rgb_images = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in images]
        
        # Ejecutar inferencia
        detections = self.model(rgb_images)
        
        # Procesar resultados
        results = []
        
        # Convertir a pandas y filtrar por clases de interés
        for i, img_dets in enumerate(detections.pandas().xyxy):
            height, width = images[i].shape[:2]
            img_results = []
            
            for _, detection in img_dets.iterrows():
                class_id = int(detection['class'])
                class_name = detection['name']
                
                # Filtrar por clases de interés
                if class_name in self.config['classes_of_interest'] or not self.config['classes_of_interest']:
                    img_results.append({
                        'class_id': class_id,
                        'class_name': class_name,
                        'confidence': float(detection['confidence']),
                        'bbox': [
                            int(detection['xmin']),
                            int(detection['ymin']),
                            int(detection['xmax']),
                            int(detection['ymax'])
                        ]
                    })
                    
            results.append(img_results)
            
        return results
        
    def visualize_detections(self, image, detections, output_path=None):
        """
        Visualizar detecciones en una imagen
        
        Args:
            image: Imagen numpy o ruta
            detections: Lista de detecciones del método detect()
            output_path: Ruta para guardar la imagen con detecciones
            
        Returns:
            Imagen con detecciones dibujadas
        """
        # Cargar imagen si es una ruta
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"No se pudo cargar la imagen: {image}")
                
        # Crear copia para no modificar la original
        vis_image = image.copy()
        
        # Colores para diferentes clases (BGR)
        colors = {
            'person': (0, 128, 255),    # Naranja
            'car': (0, 255, 0),         # Verde
            'truck': (0, 255, 128),     # Verde claro
            'bicycle': (255, 0, 0),     # Azul
            'motorcycle': (255, 0, 128),# Púrpura
            'bus': (255, 128, 0),       # Cian
            'default': (0, 255, 255)    # Amarillo
        }
        
        # Dibujar cada detección
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Obtener color para esta clase
            color = colors.get(class_name, colors['default'])
            
            # Dibujar rectángulo
            cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 2)
            
            # Preparar texto
            text = f"{class_name} {confidence:.2f}"
            
            # Fondo para el texto
            text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(vis_image, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), color, -1)
            
            # Dibujar texto
            cv2.putText(vis_image, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
            
        # Guardar imagen si se especificó una ruta
        if output_path:
            cv2.imwrite(output_path, vis_image)
            
        return vis_image 