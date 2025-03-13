import logging
import sqlite3
import json
import os
import cv2
import time
from datetime import datetime
import tempfile
import shutil

class VideoIndexer:
    def __init__(self, db_path="data/video_index.db"):
        self.db_path = db_path
        self.logger = logging.getLogger('VideoIndexer')
        self._ensure_db_exists()
        
    def _ensure_db_exists(self):
        """Asegurar que la base de datos existe y tiene las tablas necesarias"""
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Crear tabla videos
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            path TEXT,
            start_time REAL,
            end_time REAL,
            duration REAL,
            camera_id TEXT,
            frame_count INTEGER,
            thumbnail_path TEXT,
            created_at REAL
        )
        ''')
        
        # Crear tabla events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            event_id TEXT,
            event_type TEXT,
            start_time REAL,
            end_time REAL,
            metadata TEXT,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
        ''')
        
        # Crear índices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_camera_id ON videos (camera_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_videos_start_time ON videos (start_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_video_id ON events (video_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type)')
        
        conn.commit()
        conn.close()
        
    def _index_video(self, video_path, metadata=None):
        """Indexar un archivo de video y extraer metadatos"""
        try:
            if not os.path.exists(video_path):
                self.logger.error(f"Video file not found: {video_path}")
                return None
                
            # Abrir video para extraer metadatos
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.error(f"Could not open video: {video_path}")
                return None
                
            # Extraer metadatos del video
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            # Generar thumbnail
            thumbnail_path = self._generate_thumbnail(cap, video_path)
            
            # Actualizar los metadatos con información adicional
            if metadata is None:
                metadata = {}
                
            # Extraer información de tiempo desde el nombre de archivo si no hay metadatos
            if 'start_time' not in metadata and 'end_time' not in metadata:
                timestamp_str = os.path.basename(video_path).split('_')[-1].split('.')[0]
                try:
                    start_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S').timestamp()
                    metadata['start_time'] = start_time
                    metadata['end_time'] = start_time + duration
                except:
                    # Si no podemos extraer el timestamp del nombre, usar el tiempo actual
                    metadata['start_time'] = time.time() - duration
                    metadata['end_time'] = time.time()
            
            # Guardar en base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO videos 
            (filename, path, start_time, end_time, duration, camera_id, frame_count, thumbnail_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                os.path.basename(video_path),
                video_path,
                metadata.get('start_time', 0),
                metadata.get('end_time', 0),
                duration,
                metadata.get('camera_id', 'unknown'),
                frame_count,
                thumbnail_path,
                time.time()
            ))
            
            video_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            cap.release()
            
            self.logger.info(f"Video indexed: {video_path}, ID: {video_id}")
            return video_id
            
        except Exception as e:
            self.logger.error(f"Error indexing video {video_path}: {e}")
            return None
            
    def _generate_thumbnail(self, video_capture, video_path):
        """Generar thumbnail para el video"""
        try:
            # Crear directorio para thumbnails
            thumb_dir = os.path.join(os.path.dirname(self.db_path), 'thumbnails')
            os.makedirs(thumb_dir, exist_ok=True)
            
            # Generar nombre de archivo para thumbnail
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb.jpg")
            
            # Capturar frame para thumbnail (25% del video)
            frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count > 0:
                video_capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_count * 0.25))
                ret, frame = video_capture.read()
                if ret:
                    # Redimensionar si es muy grande
                    height, width = frame.shape[:2]
                    if width > 640:
                        ratio = 640.0 / width
                        frame = cv2.resize(frame, (640, int(height * ratio)))
                        
                    # Guardar thumbnail
                    cv2.imwrite(thumb_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    return thumb_path
                    
            # Si no se pudo generar thumbnail, retornar None
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating thumbnail: {e}")
            return None
            
    def index_event(self, event_data, video_path, start_time, end_time):
        """Indexar evento y su video asociado"""
        try:
            # Verificar si el video ya está indexado
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM videos WHERE path = ?', (video_path,))
            result = cursor.fetchone()
            
            if result:
                video_id = result[0]
            else:
                # Generar metadatos para indexar el video
                metadata = {
                    'camera_id': event_data.get('camera_id', 'unknown'),
                    'event_id': event_data.get('id', str(int(time.time()))),
                    'start_time': start_time,
                    'end_time': end_time
                }
                
                # Indexar el video
                video_id = self._index_video(video_path, metadata)
                if not video_id:
                    conn.close()
                    return False
            
            # Insertar evento
            cursor.execute('''
            INSERT INTO events
            (video_id, event_id, event_type, start_time, end_time, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                video_id,
                event_data.get('id', str(int(time.time()))),
                event_data.get('type', 'unknown'),
                start_time,
                end_time,
                json.dumps(event_data)
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Event indexed: {event_data.get('type', 'unknown')} for video ID {video_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error indexing event: {e}")
            return False
            
    def search_events(self, filters=None, time_range=None, object_types=None, behavior_types=None):
        """Buscar eventos que coincidan con criterios"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Para acceder a las columnas por nombre
            cursor = conn.cursor()
            
            # Construir consulta SQL
            query = '''
            SELECT e.*, v.filename, v.path, v.thumbnail_path, v.camera_id 
            FROM events e
            JOIN videos v ON e.video_id = v.id
            WHERE 1=1
            '''
            
            params = []
            
            # Filtrar por rango de tiempo
            if time_range:
                if 'start' in time_range:
                    query += " AND e.start_time >= ?"
                    params.append(time_range['start'])
                if 'end' in time_range:
                    query += " AND e.end_time <= ?"
                    params.append(time_range['end'])
                    
            # Filtrar por tipo de evento
            if filters and 'event_type' in filters:
                if isinstance(filters['event_type'], list):
                    placeholders = ','.join(['?'] * len(filters['event_type']))
                    query += f" AND e.event_type IN ({placeholders})"
                    params.extend(filters['event_type'])
                else:
                    query += " AND e.event_type = ?"
                    params.append(filters['event_type'])
                    
            # Filtrar por cámara
            if filters and 'camera_id' in filters:
                if isinstance(filters['camera_id'], list):
                    placeholders = ','.join(['?'] * len(filters['camera_id']))
                    query += f" AND v.camera_id IN ({placeholders})"
                    params.extend(filters['camera_id'])
                else:
                    query += " AND v.camera_id = ?"
                    params.append(filters['camera_id'])
                    
            # Ordenar por tiempo de inicio (más reciente primero)
            query += " ORDER BY e.start_time DESC"
            
            # Limitar resultados
            if filters and 'limit' in filters:
                query += " LIMIT ?"
                params.append(filters['limit'])
                
            # Ejecutar consulta
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Formatear resultados
            events = []
            for row in results:
                event_data = json.loads(row['metadata']) if row['metadata'] else {}
                
                # Filtrar por tipos de objetos o comportamientos si se especifican
                if object_types and not self._event_has_object_types(event_data, object_types):
                    continue
                    
                if behavior_types and not self._event_has_behavior_types(event_data, behavior_types):
                    continue
                    
                events.append({
                    'id': row['id'],
                    'event_id': row['event_id'],
                    'event_type': row['event_type'],
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'video_id': row['video_id'],
                    'video_path': row['path'],
                    'thumbnail_path': row['thumbnail_path'],
                    'camera_id': row['camera_id'],
                    'metadata': event_data
                })
                
            conn.close()
            return events
            
        except Exception as e:
            self.logger.error(f"Error searching events: {e}")
            return []
            
    def _event_has_object_types(self, event_data, object_types):
        """Verificar si el evento contiene alguno de los tipos de objetos especificados"""
        # Buscar en los metadatos del evento por objetos
        detected_objects = event_data.get('objects', [])
        if not detected_objects:
            return False
            
        # Verificar si algún objeto coincide con los tipos buscados
        for obj in detected_objects:
            if obj.get('type') in object_types or obj.get('class') in object_types:
                return True
                
        return False
        
    def _event_has_behavior_types(self, event_data, behavior_types):
        """Verificar si el evento contiene alguno de los comportamientos especificados"""
        # Buscar en los metadatos del evento por comportamientos
        behaviors = event_data.get('behaviors', [])
        if not behaviors:
            return False
            
        # Verificar si algún comportamiento coincide con los tipos buscados
        for behavior in behaviors:
            if behavior.get('type') in behavior_types:
                return True
                
        return False
        
    def get_video_details(self, video_id):
        """Obtener detalles de un video específico"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM videos WHERE id = ?
            ''', (video_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
                
            # Obtener eventos asociados
            cursor.execute('''
            SELECT * FROM events WHERE video_id = ? ORDER BY start_time
            ''', (video_id,))
            
            events = []
            for event_row in cursor.fetchall():
                events.append({
                    'id': event_row['id'],
                    'event_id': event_row['event_id'],
                    'event_type': event_row['event_type'],
                    'start_time': event_row['start_time'],
                    'end_time': event_row['end_time'],
                    'metadata': json.loads(event_row['metadata']) if event_row['metadata'] else {}
                })
                
            conn.close()
            
            # Formatear resultado
            return {
                'id': row['id'],
                'filename': row['filename'],
                'path': row['path'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'duration': row['duration'],
                'camera_id': row['camera_id'],
                'frame_count': row['frame_count'],
                'thumbnail_path': row['thumbnail_path'],
                'created_at': row['created_at'],
                'events': events
            }
            
        except Exception as e:
            self.logger.error(f"Error getting video details: {e}")
            return None
            
    def extract_clip(self, video_id, start_offset, end_offset, output_path=None):
        """Extraer un clip de un video más largo basado en tiempos de inicio y fin"""
        try:
            # Obtener detalles del video
            video_details = self.get_video_details(video_id)
            if not video_details:
                return None
                
            video_path = video_details['path']
            if not os.path.exists(video_path):
                self.logger.error(f"Video file not found: {video_path}")
                return None
                
            # Si no se especifica ruta de salida, crear una temporal
            if not output_path:
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                output_dir = os.path.join(os.path.dirname(self.db_path), 'clips')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{base_name}_clip_{int(time.time())}.mp4")
                
            # Abrir video origen
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.logger.error(f"Could not open video: {video_path}")
                return None
                
            # Obtener propiedades del video
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calcular frames de inicio y fin
            start_frame = int(start_offset * fps)
            end_frame = int(end_offset * fps)
            
            # Configurar escritor de video
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Posicionar en frame inicial
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Copiar frames al nuevo video
            current_frame = start_frame
            while current_frame <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                out.write(frame)
                current_frame += 1
                
            # Liberar recursos
            cap.release()
            out.release()
            
            self.logger.info(f"Clip extracted to {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Error extracting clip: {e}")
            return None
            
    def delete_video(self, video_id, delete_file=False):
        """Eliminar video de la base de datos y opcionalmente el archivo"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Obtener ruta del archivo antes de eliminarlo
            cursor.execute('SELECT path, thumbnail_path FROM videos WHERE id = ?', (video_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
                
            video_path, thumbnail_path = row
            
            # Eliminar eventos asociados
            cursor.execute('DELETE FROM events WHERE video_id = ?', (video_id,))
            
            # Eliminar video de la base de datos
            cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
            
            conn.commit()
            conn.close()
            
            # Opcionalmente eliminar el archivo físico
            if delete_file and os.path.exists(video_path):
                os.remove(video_path)
                
            # Eliminar thumbnail si existe
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                
            self.logger.info(f"Video {video_id} deleted from database")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting video: {e}")
            return False 