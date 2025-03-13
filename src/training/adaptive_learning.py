import os
import logging
import numpy as np
import pandas as pd
import joblib
import json
import time
from datetime import datetime, timedelta
import tensorflow as tf
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

class AdaptiveLearningSystem:
    """
    Sistema de aprendizaje adaptativo para personalización por cliente
    
    Permite ajustar los modelos de detección y análisis de comportamiento
    basado en datos históricos específicos del cliente y retroalimentación.
    """
    
    def __init__(self, config=None):
        """
        Inicializar sistema de aprendizaje adaptativo
        
        Args:
            config: Configuración del sistema de aprendizaje
        """
        self.logger = logging.getLogger('AdaptiveLearningSystem')
        self.config = config or {}
        
        # Directorio para modelos y datos de entrenamiento
        self.models_dir = self.config.get('models_dir', 'data/client_models')
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Cliente actual
        self.client_id = self.config.get('client_id', 'default')
        
        # Registro de eventos para entrenamiento
        self.event_history = []
        
        # Modelos personalizados
        self.behavior_models = {}
        self.detection_thresholds = {}
        self.zone_risk_profiles = {}
        
        # Cargar modelos existentes si hay
        self._load_client_models()
        
        self.logger.info(f"Sistema de aprendizaje adaptativo inicializado para cliente: {self.client_id}")
    
    def _load_client_models(self):
        """Cargar modelos específicos del cliente si existen"""
        client_dir = os.path.join(self.models_dir, self.client_id)
        
        if not os.path.exists(client_dir):
            os.makedirs(client_dir, exist_ok=True)
            self.logger.info(f"Creado nuevo directorio para cliente: {self.client_id}")
            return
            
        # Cargar umbrales personalizados
        thresholds_path = os.path.join(client_dir, 'detection_thresholds.json')
        if os.path.exists(thresholds_path):
            try:
                with open(thresholds_path, 'r') as f:
                    self.detection_thresholds = json.load(f)
                self.logger.info(f"Umbrales de detección cargados: {len(self.detection_thresholds)} configuraciones")
            except Exception as e:
                self.logger.error(f"Error al cargar umbrales: {e}")
                
        # Cargar perfiles de riesgo por zona
        risk_path = os.path.join(client_dir, 'zone_risk_profiles.json')
        if os.path.exists(risk_path):
            try:
                with open(risk_path, 'r') as f:
                    self.zone_risk_profiles = json.load(f)
                self.logger.info(f"Perfiles de riesgo cargados: {len(self.zone_risk_profiles)} zonas")
            except Exception as e:
                self.logger.error(f"Error al cargar perfiles de riesgo: {e}")
                
        # Cargar modelos de comportamiento
        for model_type in ['loitering', 'intrusion', 'tailgating', 'abandoned_object']:
            model_path = os.path.join(client_dir, f'{model_type}_model.pkl')
            if os.path.exists(model_path):
                try:
                    model = joblib.load(model_path)
                    self.behavior_models[model_type] = model
                    self.logger.info(f"Modelo de comportamiento '{model_type}' cargado")
                except Exception as e:
                    self.logger.error(f"Error al cargar modelo {model_type}: {e}")
    
    def register_event(self, event_data, feedback=None):
        """
        Registrar evento para entrenamiento futuro
        
        Args:
            event_data: Datos del evento detectado
            feedback: Retroalimentación opcional (true positive, false positive)
        """
        # Enriquecer datos con retroalimentación
        event_record = event_data.copy()
        event_record['registration_time'] = datetime.now().isoformat()
        
        if feedback:
            event_record['feedback'] = feedback
            
        self.event_history.append(event_record)
        
        # Guardar periódicamente si hay suficientes eventos nuevos
        if len(self.event_history) % 100 == 0:
            self._save_event_history()
            
        return True
    
    def register_simulation_data(self, simulation_data):
        """
        Registrar datos de simulación para entrenamiento
        
        Args:
            simulation_data: Lista de eventos simulados
        """
        if not simulation_data:
            return False
            
        # Marcar como datos de simulación
        for event in simulation_data:
            event['source'] = 'simulation'
            event['registration_time'] = datetime.now().isoformat()
            self.event_history.append(event)
            
        self.logger.info(f"Registrados {len(simulation_data)} eventos de simulación")
        
        # Entrenar con datos combinados
        if len(self.event_history) > 500:  # Entrenar cuando tengamos suficientes datos
            self.train_models()
            
        return True
    
    def _save_event_history(self):
        """Guardar historial de eventos para entrenamiento"""
        try:
            client_dir = os.path.join(self.models_dir, self.client_id)
            os.makedirs(client_dir, exist_ok=True)
            
            # Guardar en formato JSON
            history_path = os.path.join(client_dir, 'event_history.json')
            with open(history_path, 'w') as f:
                json.dump(self.event_history, f, indent=2)
                
            self.logger.info(f"Historial de eventos guardado: {len(self.event_history)} registros")
            return True
        except Exception as e:
            self.logger.error(f"Error al guardar historial de eventos: {e}")
            return False
    
    def train_models(self, specific_model=None):
        """
        Entrenar o reentrenar modelos con datos acumulados
        
        Args:
            specific_model: Entrenar solo un tipo específico de modelo
        
        Returns:
            Diccionario con resultados del entrenamiento
        """
        results = {}
        
        if len(self.event_history) < 100:
            self.logger.warning("Datos insuficientes para entrenamiento")
            return {"error": "Datos insuficientes", "min_required": 100}
            
        try:
            # Convertir a DataFrame para facilitar el preprocesamiento
            df = pd.DataFrame(self.event_history)
            
            # Modelos a entrenar
            models_to_train = [specific_model] if specific_model else ['loitering', 'intrusion', 'tailgating', 'abandoned_object']
            
            for model_type in models_to_train:
                if model_type not in df['type'].unique():
                    continue  # No hay datos para este tipo
                    
                # Filtrar por tipo de evento
                model_df = df[df['type'] == model_type].copy()
                
                # Preparar características según el tipo de evento
                X, y = self._prepare_features(model_df, model_type)
                
                if len(X) < 50:
                    self.logger.warning(f"Datos insuficientes para modelo {model_type}")
                    continue
                    
                # División train/test
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                
                # Entrenar modelo (RandomForest como ejemplo)
                model = RandomForestClassifier(n_estimators=100, random_state=42)
                model.fit(X_train, y_train)
                
                # Evaluar modelo
                accuracy = model.score(X_test, y_test)
                results[model_type] = {
                    "accuracy": accuracy,
                    "samples": len(X),
                    "features": X.shape[1]
                }
                
                # Guardar modelo
                self.behavior_models[model_type] = model
                self._save_model(model, model_type)
                
                self.logger.info(f"Modelo {model_type} entrenado. Precisión: {accuracy:.4f}")
                
            # Actualizar umbrales de detección basados en datos
            self._optimize_detection_thresholds(df)
            
            # Actualizar perfiles de riesgo por zona
            self._update_zone_risk_profiles(df)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error durante entrenamiento: {e}")
            return {"error": str(e)}
    
    def _prepare_features(self, df, event_type):
        """
        Preparar características para entrenamiento según tipo de evento
        
        Args:
            df: DataFrame con eventos
            event_type: Tipo de evento a modelar
            
        Returns:
            X, y para entrenamiento
        """
        # Crear etiquetas (1 para eventos confirmados, 0 para falsos positivos)
        y = np.ones(len(df))
        
        if 'feedback' in df.columns:
            mask = df['feedback'] == 'false_positive'
            y[mask] = 0
        
        feature_columns = []
        
        # Extraer características según tipo de evento
        if event_type == 'loitering':
            # Características para detección de merodeo
            if 'duration' in df.columns:
                df['duration_sec'] = df['duration'].apply(lambda x: x if isinstance(x, (int, float)) else 0)
                feature_columns.append('duration_sec')
                
            if 'details' in df.columns:
                # Extraer características del diccionario de detalles
                df['movement_radius'] = df['details'].apply(
                    lambda x: x.get('radius', 0) if isinstance(x, dict) else 0
                )
                df['detection_confidence'] = df['details'].apply(
                    lambda x: x.get('confidence', 0) if isinstance(x, dict) else 0
                )
                feature_columns.extend(['movement_radius', 'detection_confidence'])
                
        elif event_type == 'intrusion':
            # Características para detección de intrusión
            if 'details' in df.columns:
                df['zone_type'] = df['details'].apply(
                    lambda x: x.get('zone_type', 'unknown') if isinstance(x, dict) else 'unknown'
                )
                
                # Convertir zona a numérico
                zone_mapping = {zone: i for i, zone in enumerate(df['zone_type'].unique())}
                df['zone_type_id'] = df['zone_type'].map(zone_mapping)
                
                df['detection_confidence'] = df['details'].apply(
                    lambda x: x.get('confidence', 0) if isinstance(x, dict) else 0
                )
                
                feature_columns.extend(['zone_type_id', 'detection_confidence'])
                
        elif event_type in ['tailgating', 'abandoned_object']:
            # Características para otros tipos de eventos
            if 'details' in df.columns:
                df['detection_confidence'] = df['details'].apply(
                    lambda x: x.get('confidence', 0) if isinstance(x, dict) else 0
                )
                feature_columns.append('detection_confidence')
        
        # Añadir hora del día como característica
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            feature_columns.append('hour')
            
        # Asegurar que tenemos al menos una característica
        if not feature_columns:
            # Usar cualquier columna numérica disponible
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                feature_columns = numeric_cols
            else:
                # Si no hay columnas numéricas, crear una
                df['dummy'] = 1
                feature_columns = ['dummy']
                
        X = df[feature_columns].fillna(0).values
        return X, y
    
    def _optimize_detection_thresholds(self, df):
        """
        Optimizar umbrales de detección basados en datos históricos
        
        Args:
            df: DataFrame con eventos históricos
        """
        # Optimizar por tipo de evento
        for event_type in df['type'].unique():
            type_df = df[df['type'] == event_type]
            
            # Solo optimizar si tenemos feedback
            if 'feedback' in type_df.columns and not type_df['feedback'].isna().all():
                confirmed_df = type_df[type_df['feedback'] == 'true_positive']
                rejected_df = type_df[type_df['feedback'] == 'false_positive']
                
                if len(confirmed_df) > 10 and len(rejected_df) > 5:
                    # Analizar niveles de confianza
                    conf_values = []
                    
                    for _, row in type_df.iterrows():
                        if 'confidence' in row and isinstance(row['confidence'], (int, float)):
                            conf_values.append(row['confidence'])
                        elif 'details' in row and isinstance(row['details'], dict) and 'confidence' in row['details']:
                            conf_values.append(row['details']['confidence'])
                            
                    if conf_values:
                        # Encontrar umbral óptimo (simplificado)
                        new_threshold = np.percentile(conf_values, 25)  # Usar percentil 25 como umbral
                        
                        # Evitar umbrales extremos
                        new_threshold = max(0.3, min(0.8, new_threshold))
                        
                        self.detection_thresholds[event_type] = new_threshold
                        self.logger.info(f"Umbral optimizado para {event_type}: {new_threshold:.2f}")
            
        # Guardar umbrales
        if self.detection_thresholds:
            self._save_detection_thresholds()
    
    def _update_zone_risk_profiles(self, df):
        """
        Actualizar perfiles de riesgo por zona basados en eventos históricos
        
        Args:
            df: DataFrame con eventos históricos
        """
        # Verificar si tenemos datos de zona
        if 'details' not in df.columns:
            return
            
        # Extraer zonas de los detalles
        zones = set()
        for _, row in df.iterrows():
            if isinstance(row['details'], dict) and 'zone' in row['details']:
                zones.add(row['details']['zone'])
                
        # Para cada zona, calcular perfil de riesgo
        for zone in zones:
            # Filtrar eventos en esta zona
            zone_events = []
            for _, row in df.iterrows():
                if isinstance(row['details'], dict) and row['details'].get('zone') == zone:
                    zone_events.append(row)
                    
            if len(zone_events) < 5:
                continue
                
            # Calcular distribución de tipos de eventos
            event_types = {}
            for event in zone_events:
                event_type = event['type']
                if event_type not in event_types:
                    event_types[event_type] = 0
                event_types[event_type] += 1
                
            # Calcular horas de mayor actividad
            hours = [0] * 24
            for event in zone_events:
                if 'timestamp' in event:
                    try:
                        hour = datetime.fromisoformat(event['timestamp']).hour
                        hours[hour] += 1
                    except:
                        pass
                        
            # Crear perfil de riesgo
            risk_profile = {
                'event_distribution': event_types,
                'total_events': len(zone_events),
                'active_hours': hours,
                'last_updated': datetime.now().isoformat()
            }
            
            # Calcular nivel de riesgo (0-100)
            events_per_day = len(zone_events) / max(1, (datetime.now() - datetime.fromisoformat(zone_events[0]['timestamp'])).days)
            risk_level = min(100, events_per_day * 10)  # 10 eventos/día = riesgo máximo
            risk_profile['risk_level'] = risk_level
            
            # Guardar perfil
            self.zone_risk_profiles[zone] = risk_profile
            
        # Guardar perfiles
        if self.zone_risk_profiles:
            self._save_zone_risk_profiles()
    
    def _save_model(self, model, model_type):
        """Guardar modelo entrenado"""
        try:
            client_dir = os.path.join(self.models_dir, self.client_id)
            os.makedirs(client_dir, exist_ok=True)
            
            model_path = os.path.join(client_dir, f'{model_type}_model.pkl')
            joblib.dump(model, model_path)
            
            self.logger.info(f"Modelo {model_type} guardado en {model_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error al guardar modelo {model_type}: {e}")
            return False
    
    def _save_detection_thresholds(self):
        """Guardar umbrales de detección optimizados"""
        try:
            client_dir = os.path.join(self.models_dir, self.client_id)
            os.makedirs(client_dir, exist_ok=True)
            
            thresholds_path = os.path.join(client_dir, 'detection_thresholds.json')
            with open(thresholds_path, 'w') as f:
                json.dump(self.detection_thresholds, f, indent=2)
                
            self.logger.info(f"Umbrales de detección guardados: {len(self.detection_thresholds)} configuraciones")
            return True
        except Exception as e:
            self.logger.error(f"Error al guardar umbrales: {e}")
            return False
    
    def _save_zone_risk_profiles(self):
        """Guardar perfiles de riesgo por zona"""
        try:
            client_dir = os.path.join(self.models_dir, self.client_id)
            os.makedirs(client_dir, exist_ok=True)
            
            risk_path = os.path.join(client_dir, 'zone_risk_profiles.json')
            with open(risk_path, 'w') as f:
                json.dump(self.zone_risk_profiles, f, indent=2)
                
            self.logger.info(f"Perfiles de riesgo guardados: {len(self.zone_risk_profiles)} zonas")
            return True
        except Exception as e:
            self.logger.error(f"Error al guardar perfiles de riesgo: {e}")
            return False
            
    def get_optimized_parameters(self, camera_id=None, zone_id=None, event_type=None):
        """
        Obtener parámetros optimizados específicos
        
        Args:
            camera_id: ID de cámara opcional
            zone_id: ID de zona opcional
            event_type: Tipo de evento opcional
            
        Returns:
            Diccionario con parámetros optimizados
        """
        result = {
            'client_id': self.client_id,
            'updated_at': datetime.now().isoformat()
        }
        
        # Añadir umbrales de detección
        if event_type and event_type in self.detection_thresholds:
            result['detection_threshold'] = self.detection_thresholds[event_type]
        elif not event_type:
            result['detection_thresholds'] = self.detection_thresholds
            
        # Añadir perfil de riesgo de zona
        if zone_id and zone_id in self.zone_risk_profiles:
            result['zone_risk_profile'] = self.zone_risk_profiles[zone_id]
        elif not zone_id:
            # Incluir zonas de mayor riesgo
            high_risk_zones = {}
            for zone_id, profile in self.zone_risk_profiles.items():
                if profile.get('risk_level', 0) > 50:  # Zonas de alto riesgo
                    high_risk_zones[zone_id] = profile
            
            if high_risk_zones:
                result['high_risk_zones'] = high_risk_zones
        
        return result
    
    def run_scenario_simulation(self, scenario_config):
        """
        Ejecutar simulación de escenario para entrenamiento
        
        Args:
            scenario_config: Configuración del escenario a simular
            
        Returns:
            Resultados de la simulación
        """
        try:
            scenario_type = scenario_config.get('type', 'random')
            num_events = scenario_config.get('num_events', 100)
            event_types = scenario_config.get('event_types', ['intrusion', 'loitering', 'tailgating'])
            
            self.logger.info(f"Iniciando simulación de escenario: {scenario_type} con {num_events} eventos")
            
            # Generar eventos simulados
            simulated_events = []
            
            if scenario_type == 'random':
                simulated_events = self._generate_random_events(num_events, event_types)
            elif scenario_type == 'intrusion_sequence':
                simulated_events = self._simulate_intrusion_sequence(scenario_config)
            elif scenario_type == 'tailgating_sequence':
                simulated_events = self._simulate_tailgating_sequence(scenario_config)
            
            # Registrar eventos para entrenamiento
            if simulated_events:
                self.register_simulation_data(simulated_events)
                
            return {
                'status': 'success',
                'events_generated': len(simulated_events),
                'simulation_id': str(int(time.time()))
            }
            
        except Exception as e:
            self.logger.error(f"Error en simulación de escenario: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _generate_random_events(self, num_events, event_types):
        """Generar eventos aleatorios para simulación"""
        events = []
        base_time = datetime.now() - timedelta(days=7)  # Una semana atrás
        
        for i in range(num_events):
            event_type = np.random.choice(event_types)
            
            # Timestamp aleatorio en la última semana
            random_minutes = np.random.randint(0, 7 * 24 * 60)
            timestamp = (base_time + timedelta(minutes=random_minutes)).isoformat()
            
            # Crear evento simulado
            event = {
                'type': event_type,
                'timestamp': timestamp,
                'camera_id': f"cam_{np.random.randint(1, 5)}",
                'confidence': np.random.uniform(0.5, 0.95),
                'source': 'simulation',
                'details': {}
            }
            
            # Detalles específicos según tipo
            if event_type == 'intrusion':
                event['details'] = {
                    'zone': f"zone_{np.random.randint(1, 4)}",
                    'zone_type': np.random.choice(['restricted', 'secure', 'monitored']),
                    'duration': np.random.randint(5, 60)
                }
            elif event_type == 'loitering':
                event['details'] = {
                    'duration': np.random.randint(30, 300),
                    'radius': np.random.randint(10, 100)
                }
            elif event_type == 'tailgating':
                event['details'] = {
                    'follower_distance': np.random.randint(5, 30),
                    'time_gap': np.random.uniform(0.5, 3.0)
                }
                
            events.append(event)
            
        return events
    
    def _simulate_intrusion_sequence(self, config):
        """Simular secuencia de intrusión"""
        num_events = config.get('num_events', 20)
        zone_id = config.get('zone_id', 'zone_1')
        camera_id = config.get('camera_id', 'cam_1')
        
        events = []
        base_time = datetime.now() - timedelta(hours=24)
        
        # Simular secuencia de acercamiento a zona restringida
        for i in range(num_events):
            progress = i / num_events  # 0 -> 1
            
            # En etapas tempranas, solo acercamiento
            if progress < 0.3:
                event_type = 'loitering'
                confidence = np.random.uniform(0.5, 0.7)
                details = {
                    'duration': np.random.randint(10, 60),
                    'radius': np.random.randint(50, 100),
                    'distance_to_zone': int(100 * (1 - progress))
                }
            # Etapa media, intentos
            elif progress < 0.7:
                event_type = np.random.choice(['loitering', 'intrusion'], p=[0.7, 0.3])
                confidence = np.random.uniform(0.6, 0.8)
                details = {
                    'zone': zone_id,
                    'zone_type': 'restricted',
                    'duration': np.random.randint(5, 30),
                    'partial_entry': True
                }
            # Etapa final, intrusión completa
            else:
                event_type = 'intrusion'
                confidence = np.random.uniform(0.7, 0.95)
                details = {
                    'zone': zone_id,
                    'zone_type': 'restricted',
                    'duration': np.random.randint(10, 120),
                    'complete_entry': True
                }
                
            # Timestamp progresivo
            timestamp = (base_time + timedelta(minutes=i*15)).isoformat()
            
            event = {
                'type': event_type,
                'timestamp': timestamp,
                'camera_id': camera_id,
                'confidence': confidence,
                'source': 'simulation',
                'details': details
            }
            
            events.append(event)
            
        return events
    
    def _simulate_tailgating_sequence(self, config):
        """Simular secuencia de tailgating (seguimiento no autorizado)"""
        num_events = config.get('num_events', 15)
        zone_id = config.get('zone_id', 'entrance_1')
        camera_id = config.get('camera_id', 'cam_1')
        
        events = []
        base_time = datetime.now() - timedelta(hours=12)
        
        # Simular varios intentos de tailgating
        for i in range(num_events):
            # Variar tiempo entre eventos
            timestamp = (base_time + timedelta(minutes=i*30 + np.random.randint(0, 15))).isoformat()
            
            # Simular acceso autorizado seguido por no autorizado
            if i % 3 == 0:  # Cada 3 eventos, persona autorizada
                event_type = 'authorized_access'
                confidence = 0.9
                person_id = f"employee_{np.random.randint(1, 20)}"
                details = {
                    'zone': zone_id,
                    'person_id': person_id,
                    'access_method': np.random.choice(['card', 'biometric']),
                    'success': True
                }
            else:  # Intentos de tailgating
                event_type = 'tailgating'
                confidence = np.random.uniform(0.6, 0.9)
                details = {
                    'zone': zone_id,
                    'follower_distance': np.random.randint(5, 30),
                    'time_gap': np.random.uniform(0.5, 5.0),
                    'leader_id': f"employee_{np.random.randint(1, 20)}",
                    'success': np.random.random() > 0.5
                }
                
            event = {
                'type': event_type,
                'timestamp': timestamp,
                'camera_id': camera_id,
                'confidence': confidence,
                'source': 'simulation',
                'details': details
            }
            
            events.append(event)
            
        return events 