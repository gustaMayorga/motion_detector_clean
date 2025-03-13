from src.agent_modules.base.agent_base import BaseAgent, AgentConfig
from typing import Dict, Any, Optional, List
import cv2
import numpy as np
from datetime import datetime
import asyncio
from src.core.ml_engine.face_recognition import FaceRecognizer
from src.agent_modules.access_control.hardware_controller import AccessHardwareController
from src.core.ml_engine.plate_recognition import PlateRecognizer
from pathlib import Path
import json

class AccessControlAgent(BaseAgent):
    def __init__(self, config: Dict[str, Any], event_bus, logger):
        super().__init__(config, event_bus, logger)
        self.active_sessions = {}
        self.pending_authorizations = {}
        self.access_rules = self._load_access_rules()
        
        # Inicializar componentes
        self.face_recognizer = FaceRecognizer(config['face_recognition'])
        self.hardware = AccessHardwareController(config['hardware'])
        self.plate_recognizer = PlateRecognizer()
        
        # Hardware
        self.card_reader = RFIDReader(config['hardware']['card_reader'])
        self.gpio = GPIOController(config['hardware']['gpio'])
        
        # Estado
        self.failed_attempts: Dict[str, List[datetime]] = {}
        
        # Cache de usuarios autorizados
        self.authorized_users: Dict[str, Dict[str, Any]] = {}
        self._load_authorized_users()
        
    async def start(self):
        """Inicia el agente de control de acceso"""
        await super().start()
        
        try:
            # Inicializar hardware
            await self.card_reader.initialize()
            await self.gpio.initialize()
            
            # Iniciar loops de procesamiento
            self.tasks = [
                asyncio.create_task(self._process_card_reads()),
                asyncio.create_task(self._process_face_recognition()),
                asyncio.create_task(self._cleanup_expired_sessions())
            ]
            
            while self.running:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            await self.handle_error(e)
            
        finally:
            for task in self.tasks:
                task.cancel()
            
    async def stop(self):
        """Detiene el agente"""
        self.running = False
        await self.card_reader.cleanup()
        await self.gpio.cleanup()
        await super().stop()
        
    async def _process_card_reads(self):
        """Procesa lecturas de tarjetas RFID"""
        while self.running:
            try:
                card_data = await self.card_reader.read()
                if card_data:
                    await self._handle_card_access(card_data)
                    
            except Exception as e:
                await self.handle_error(e)
                await asyncio.sleep(1)
                
    async def _process_face_recognition(self):
        """Procesa reconocimiento facial"""
        cap = cv2.VideoCapture(self.config['camera_source'])
        
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    continue
                    
                # Detectar y reconocer rostros
                faces = await self.face_recognizer.identify_faces(frame)
                
                for face in faces:
                    await self._handle_face_access(face, frame)
                    
                await asyncio.sleep(0.1)
                
        finally:
            cap.release()
            
    async def _handle_card_access(self, card_data: str):
        """Maneja un intento de acceso con tarjeta"""
        user_id = self._get_user_by_card(card_data)
        
        if not user_id:
            await self._handle_unauthorized_access("card_invalid", card_data)
            return
            
        if not self._check_user_schedule(user_id):
            await self._handle_unauthorized_access("schedule_violation", user_id)
            return
            
        await self._grant_access(user_id, "card")
        
    async def _handle_face_access(self, face_data: Dict[str, Any], frame: np.ndarray):
        """Maneja un intento de acceso por reconocimiento facial"""
        user_id = face_data['user_id']
        confidence = face_data['confidence']
        
        if confidence < self.config['face_recognition']['min_confidence']:
            await self._handle_unauthorized_access("face_low_confidence", user_id)
            return
            
        if not self._check_user_schedule(user_id):
            await self._handle_unauthorized_access("schedule_violation", user_id)
            return
            
        # Guardar foto de verificación si está configurado
        if self.config.get('save_verification_photos', True):
            await self._save_verification_photo(frame, user_id)
            
        await self._grant_access(user_id, "face")
        
    async def _grant_access(self, user_id: str, method: str):
        """Concede acceso a un usuario"""
        user = self.authorized_users.get(user_id)
        if not user:
            return
            
        # Activar relé/barrera
        barrier_pin = self.config['hardware']['gpio']['barrier_pin']
        await self.gpio.set_pin(barrier_pin, True)
        
        # Registrar sesión
        session_id = f"{user_id}_{datetime.now():%Y%m%d_%H%M%S}"
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'start_time': datetime.now(),
            'method': method
        }
        
        # Emitir evento
        await self.emit_event(
            "access_granted",
            {
                "user_id": user_id,
                "name": user['name'],
                "access_point": self.config['access_point_id'],
                "method": method,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Programar cierre de barrera
        await asyncio.sleep(self.config['barrier_open_time'])
        await self.gpio.set_pin(barrier_pin, False)
        
    async def _handle_unauthorized_access(self, reason: str, identifier: str):
        """Maneja un intento de acceso no autorizado"""
        # Registrar intento fallido
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
            
        self.failed_attempts[identifier].append(datetime.now())
        
        # Verificar bloqueo
        if len(self.failed_attempts[identifier]) >= self.config['max_failed_attempts']:
            await self._handle_lockout(identifier)
            
        # Emitir evento
        await self.emit_event(
            "access_denied",
            {
                "identifier": identifier,
                "reason": reason,
                "access_point": self.config['access_point_id'],
                "timestamp": datetime.now().isoformat()
            },
            priority=3
        )
        
    def _check_user_schedule(self, user_id: str) -> bool:
        """Verifica si el usuario tiene permitido el acceso en el horario actual"""
        user = self.authorized_users.get(user_id)
        if not user:
            return False
            
        current_time = datetime.now()
        schedules = user.get('schedules', [])
        
        for schedule in schedules:
            if self._is_in_schedule(current_time, schedule):
                return True
                
        return False
        
    def _load_authorized_users(self):
        """Carga la lista de usuarios autorizados"""
        users_file = Path(self.config['users_db_path'])
        if not users_file.exists():
            self.logger.logger.warning("Base de datos de usuarios no encontrada")
            return
            
        with open(users_file) as f:
            users_data = json.load(f)
            
        self.authorized_users = {
            user['id']: user
            for user in users_data
        }
        
    async def _cleanup_expired_sessions(self):
        """Limpia sesiones expiradas"""
        while self.running:
            current_time = datetime.now()
            
            # Limpiar sesiones antiguas
            self.active_sessions = {
                session_id: session
                for session_id, session in self.active_sessions.items()
                if (current_time - session['start_time']).total_seconds() < 3600
            }
            
            # Limpiar intentos fallidos antiguos
            for identifier in list(self.failed_attempts.keys()):
                self.failed_attempts[identifier] = [
                    attempt
                    for attempt in self.failed_attempts[identifier]
                    if (current_time - attempt).total_seconds() < 3600
                ]
                
                if not self.failed_attempts[identifier]:
                    del self.failed_attempts[identifier]
                    
            await asyncio.sleep(60)
        
    def _load_access_rules(self) -> Dict[str, Any]:
        """Carga reglas de acceso desde la configuración"""
        return self.config.get('access_rules', {
            'vehicles': {'whitelist': set(), 'temporary': {}},
            'residents': set(),
            'visitors': {}
        }) 

    def _check_visitor_vehicle(self, plate: str) -> bool:
        """Verifica si el vehículo pertenece a un visitante autorizado"""
        for visitor in self.access_rules['visitors'].values():
            if visitor.get('vehicle_plate') == plate and visitor['status'] == 'active':
                return True
        return False 