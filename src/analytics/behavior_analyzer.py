import json
import numpy as np
from datetime import datetime
import os
from collections import defaultdict

class BehaviorAnalyzer:
    def __init__(self, rules_config="configs/behavior_rules.json"):
        self.rules = self._load_rules(rules_config)
        self.state_history = {}  # Historial de estados para cada objeto rastreado
        self.zone_definitions = {}  # Definiciones de zonas en la escena
        self.event_history = defaultdict(list)  # Historial de eventos detectados
        
    def _load_rules(self, config_path):
        """Cargar reglas de comportamiento desde archivo JSON"""
        if not os.path.exists(config_path):
            # Si no existe el archivo, usar reglas predeterminadas
            return {
                "retail": {
                    "loitering": {
                        "time_threshold": 60,  # segundos
                        "zone_ids": ["high_value_area", "cashier_area"]
                    },
                    "item_concealment": {
                        "pattern": "pick_and_conceal",
                        "detection_confidence": 0.7
                    },
                    "erratic_movement": {
                        "direction_changes_threshold": 6,
                        "time_window": 30  # segundos
                    }
                },
                "residential": {
                    "perimeter_breach": {
                        "zone_ids": ["perimeter"],
                        "time_threshold": 10  # segundos
                    },
                    "tailgating": {
                        "time_threshold": 5,  # segundos
                        "distance_threshold": 2.0  # metros
                    },
                    "loitering": {
                        "time_threshold": 120,  # segundos
                        "zone_ids": ["entrance", "restricted_area"]
                    }
                }
            }
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rules configuration: {e}")
            return {}
            
    def set_zone_definitions(self, zones):
        """Establecer definiciones de zonas en la escena"""
        self.zone_definitions = zones
        
    def _is_in_zone(self, position, zone_id):
        """Determinar si una posición está dentro de una zona definida"""
        if zone_id not in self.zone_definitions:
            return False
            
        zone = self.zone_definitions[zone_id]
        if zone['type'] == 'polygon':
            # Comprobar si el punto está dentro del polígono
            import cv2
            point = np.array(position, dtype=np.int32)
            polygon = np.array(zone['coordinates'], dtype=np.int32)
            result = cv2.pointPolygonTest(polygon, (point[0], point[1]), False)
            return result >= 0
        elif zone['type'] == 'rectangle':
            # Comprobar si el punto está dentro del rectángulo
            x, y = position
            x1, y1, x2, y2 = zone['coordinates']
            return (x1 <= x <= x2) and (y1 <= y <= y2)
            
        return False
        
    def _update_track_state(self, track_id, current_data, timestamp):
        """Actualizar historial de estado para un objeto rastreado"""
        if track_id not in self.state_history:
            self.state_history[track_id] = []
            
        # Añadir nueva entrada al historial
        self.state_history[track_id].append({
            'timestamp': timestamp,
            'position': current_data.get('centroid', current_data.get('position')),
            'bbox': current_data.get('bbox'),
            'velocity': current_data.get('velocity'),
            'activity': current_data.get('activity')
        })
        
        # Mantener solo el historial reciente (últimos 2 minutos)
        cutoff_time = timestamp - 120  # 2 minutos en segundos
        self.state_history[track_id] = [
            state for state in self.state_history[track_id] 
            if state['timestamp'] >= cutoff_time
        ]
        
    def analyze(self, track_id, track_data, scene_context):
        """Analizar comportamiento de un objeto rastreado"""
        # Actualizar estado del objeto
        timestamp = scene_context.get('timestamp', datetime.now().timestamp())
        self._update_track_state(track_id, track_data, timestamp)
        
        # Analizar comportamientos basados en el contexto de la escena
        scene_type = scene_context.get('type', 'retail')  # Por defecto, asumir retail
        
        detected_behaviors = []
        
        if scene_type == 'retail':
            retail_behaviors = self._analyze_retail_behaviors(track_id, scene_context)
            detected_behaviors.extend(retail_behaviors)
        elif scene_type == 'residential':
            residential_behaviors = self._analyze_residential_behaviors(track_id, scene_context)
            detected_behaviors.extend(residential_behaviors)
            
        # Registrar comportamientos detectados
        if detected_behaviors:
            self.event_history[track_id].extend([
                {'behavior': b, 'timestamp': timestamp} for b in detected_behaviors
            ])
            
        return detected_behaviors
        
    def _analyze_retail_behaviors(self, track_id, scene_context):
        """Analizar comportamientos específicos de retail"""
        behaviors = []
        history = self.state_history.get(track_id, [])
        
        if not history:
            return behaviors
            
        # Comprobar permanencia (loitering)
        loitering = self._detect_loitering(track_id, 'retail', scene_context)
        if loitering:
            behaviors.append({
                'type': 'loitering',
                'confidence': loitering['confidence'],
                'zone': loitering['zone'],
                'duration': loitering['duration']
            })
            
        # Comprobar movimiento errático
        erratic = self._detect_erratic_movement(track_id, scene_context)
        if erratic:
            behaviors.append({
                'type': 'erratic_movement',
                'confidence': erratic['confidence'],
                'changes': erratic['changes']
            })
            
        return behaviors
        
    def _analyze_residential_behaviors(self, track_id, scene_context):
        """Analizar comportamientos específicos de áreas residenciales"""
        behaviors = []
        history = self.state_history.get(track_id, [])
        
        if not history:
            return behaviors
            
        # Comprobar violación de perímetro
        breach = self._detect_perimeter_breach(track_id, scene_context)
        if breach:
            behaviors.append({
                'type': 'perimeter_breach',
                'confidence': breach['confidence'],
                'zone': breach['zone']
            })
            
        # Comprobar permanencia (loitering)
        loitering = self._detect_loitering(track_id, 'residential', scene_context)
        if loitering:
            behaviors.append({
                'type': 'loitering',
                'confidence': loitering['confidence'],
                'zone': loitering['zone'],
                'duration': loitering['duration']
            })
            
        return behaviors
        
    def _detect_loitering(self, track_id, scene_type, scene_context):
        """Detectar permanencia prolongada en un área"""
        history = self.state_history.get(track_id, [])
        if len(history) < 2:
            return None
            
        # Obtener configuración según el tipo de escena
        if scene_type not in self.rules:
            return None
            
        loitering_config = self.rules[scene_type].get('loitering', {})
        time_threshold = loitering_config.get('time_threshold', 60)  # segundos
        zone_ids = loitering_config.get('zone_ids', [])
        
        # Determinar zona actual del objeto
        current_position = history[-1]['position']
        current_zone = None
        
        for zone_id in zone_ids:
            if self._is_in_zone(current_position, zone_id):
                current_zone = zone_id
                break
                
        if not current_zone:
            return None
            
        # Verificar cuánto tiempo ha estado en esta zona
        zone_entry_time = None
        for state in reversed(history):
            pos = state['position']
            if self._is_in_zone(pos, current_zone):
                zone_entry_time = state['timestamp']
            else:
                break
                
        if zone_entry_time is None:
            return None
            
        current_time = scene_context.get('timestamp', datetime.now().timestamp())
        duration = current_time - zone_entry_time
        
        if duration >= time_threshold:
            confidence = min(1.0, duration / (time_threshold * 2))  # Mayor duración, mayor confianza
            return {
                'confidence': confidence,
                'zone': current_zone,
                'duration': duration
            }
            
        return None
        
    def _detect_erratic_movement(self, track_id, scene_context):
        """Detectar movimiento errático (cambios frecuentes de dirección)"""
        history = self.state_history.get(track_id, [])
        if len(history) < 4:  # Necesitamos al menos 4 puntos para detectar cambios de dirección
            return None
            
        erratic_config = self.rules.get('retail', {}).get('erratic_movement', {})
        direction_threshold = erratic_config.get('direction_changes_threshold', 6)
        time_window = erratic_config.get('time_window', 30)  # segundos
        
        # Filtrar historial para obtener solo los últimos N segundos
        current_time = scene_context.get('timestamp', datetime.now().timestamp())
        cutoff_time = current_time - time_window
        recent_history = [state for state in history if state['timestamp'] >= cutoff_time]
        
        if len(recent_history) < 4:
            return None
            
        # Calcular cambios de dirección
        directions = []
        for i in range(1, len(recent_history)):
            prev_pos = recent_history[i-1]['position']
            curr_pos = recent_history[i]['position']
            dx = curr_pos[0] - prev_pos[0]
            dy = curr_pos[1] - prev_pos[1]
            angle = np.arctan2(dy, dx)  # Ángulo en radianes
            directions.append(angle)
            
        # Contar cambios significativos de dirección
        direction_changes = 0
        for i in range(1, len(directions)):
            # Detectar cambio de dirección significativo (más de 45 grados)
            diff = abs(directions[i] - directions[i-1])
            if diff > np.pi:
                diff = 2 * np.pi - diff  # Manejar el caso especial alrededor de -pi/pi
            if diff > np.pi / 4:  # Cambio de más de 45 grados
                direction_changes += 1
                
        if direction_changes >= direction_threshold:
            confidence = min(1.0, direction_changes / (direction_threshold * 1.5))
            return {
                'confidence': confidence,
                'changes': direction_changes
            }
            
        return None
        
    def _detect_perimeter_breach(self, track_id, scene_context):
        """Detectar violación de perímetro"""
        history = self.state_history.get(track_id, [])
        if len(history) < 2:
            return None
            
        perimeter_config = self.rules.get('residential', {}).get('perimeter_breach', {})
        zone_ids = perimeter_config.get('zone_ids', ['perimeter'])
        time_threshold = perimeter_config.get('time_threshold', 10)  # segundos
        
        # Verificar si el objeto está en una zona de perímetro
        current_position = history[-1]['position']
        current_zone = None
        
        for zone_id in zone_ids:
            if self._is_in_zone(current_position, zone_id):
                current_zone = zone_id
                break
                
        if not current_zone:
            return None
            
        # Verificar cuánto tiempo ha estado en la zona de perímetro
        zone_entry_time = None
        for state in reversed(history):
            pos = state['position']
            if self._is_in_zone(pos, current_zone):
                zone_entry_time = state['timestamp']
            else:
                break
                
        if zone_entry_time is None:
            return None
            
        current_time = scene_context.get('timestamp', datetime.now().timestamp())
        duration = current_time - zone_entry_time
        
        if duration >= time_threshold:
            confidence = min(1.0, duration / (time_threshold * 2))
            return {
                'confidence': confidence,
                'zone': current_zone
            }
            
        return None
        
    def detect_theft_patterns(self, tracks, scene):
        """Detectar patrones específicos de hurto en retail"""
        theft_patterns = []
        
        # Iterar sobre todos los objetos rastreados
        for track in tracks:
            track_id = track['id']
            
            # Analizar comportamiento individual
            behaviors = self.analyze(track_id, track, scene)
            
            # Si hay comportamientos sospechosos, evaluar como posible hurto
            suspicious_behaviors = [b for b in behaviors if b['confidence'] > 0.6]
            
            if len(suspicious_behaviors) >= 2:
                # Múltiples comportamientos sospechosos indican mayor probabilidad de hurto
                theft_patterns.append({
                    'track_id': track_id,
                    'confidence': max(b['confidence'] for b in suspicious_behaviors),
                    'behaviors': suspicious_behaviors,
                    'timestamp': scene.get('timestamp', datetime.now().timestamp())
                })
            elif any(b['type'] == 'item_concealment' for b in behaviors):
                # Ocultamiento de artículos es un fuerte indicador de hurto
                theft_patterns.append({
                    'track_id': track_id,
                    'confidence': next(b['confidence'] for b in behaviors if b['type'] == 'item_concealment'),
                    'behaviors': [b for b in behaviors if b['type'] == 'item_concealment'],
                    'timestamp': scene.get('timestamp', datetime.now().timestamp())
                })
                
        return theft_patterns 