from typing import Dict, Any, List
import asyncio
from pathlib import Path
from src.config.base_config import ConfigManager
from src.utils.logging import SecurityLogger
from src.core.event_system import EventBus
from src.agent_modules.video_analytics.video_agent import VideoAgent
from src.agent_modules.access_control.access_agent import AccessControlAgent
from src.services.alert_manager import AlertManager
from src.services.visitor_management import VisitorManager
from src.services.notification.whatsapp_service import WhatsAppService
from src.agent_modules.base import BaseAgent

class SystemController:
    def __init__(self, config_path: Path):
        # Cargar configuración
        self.config_manager = ConfigManager(config_path)
        self.system_config = self.config_manager.get_system_config()
        
        # Inicializar componentes core
        self.event_bus = EventBus()
        self.logger = SecurityLogger(self.system_config['logging'])
        
        # Inicializar servicios
        self.alert_manager = AlertManager(self.system_config['alerts'])
        self.visitor_manager = VisitorManager(self.system_config['visitors'])
        
        # Inicializar agentes
        self.agents: List[BaseAgent] = []
        self._initialize_agents()
        
        # Configurar manejadores de eventos
        self._setup_event_handlers()
        
    def _initialize_agents(self):
        """Inicializa los agentes del sistema"""
        # Video Analytics
        for camera_id, camera_config in self.system_config['cameras'].items():
            agent_config = self.config_manager.get_agent_config('video')
            agent_config.update({'camera_id': camera_id, **camera_config})
            
            self.agents.append(VideoAgent(
                agent_config,
                self.event_bus,
                self.logger
            ))
            
        # Control de Acceso
        for point_id, point_config in self.system_config['access_points'].items():
            agent_config = self.config_manager.get_agent_config('access')
            agent_config.update({'point_id': point_id, **point_config})
            
            self.agents.append(AccessControlAgent(
                agent_config,
                self.event_bus,
                self.logger
            ))
            
    def _setup_event_handlers(self):
        """Configura los manejadores de eventos del sistema"""
        # Eventos de seguridad
        self.event_bus.subscribe(
            "security_alert",
            self._handle_security_alert
        )
        
        # Eventos de acceso
        self.event_bus.subscribe(
            "access_request",
            self._handle_access_request
        )
        
        # Eventos de estado de agentes
        self.event_bus.subscribe(
            "agent_status_changed",
            self._handle_agent_status
        )
        
    async def start(self):
        """Inicia el sistema"""
        try:
            self.logger.logger.info("Iniciando sistema de seguridad...")
            
            # Iniciar agentes
            agent_tasks = []
            for agent in self.agents:
                self.logger.logger.info(f"Iniciando agente: {agent.__class__.__name__}")
                agent_tasks.append(asyncio.create_task(agent.start()))
                
            # Esperar señal de terminación
            await asyncio.gather(*agent_tasks)
            
        except Exception as e:
            self.logger.logger.error(f"Error en el sistema: {str(e)}")
            await self.shutdown()
            
    async def shutdown(self):
        """Detiene el sistema de manera ordenada"""
        self.logger.logger.info("Deteniendo sistema...")
        
        # Detener agentes
        for agent in self.agents:
            try:
                await agent.stop()
                self.logger.logger.info(f"Agente detenido: {agent.__class__.__name__}")
            except Exception as e:
                self.logger.logger.error(f"Error deteniendo agente {agent.__class__.__name__}: {str(e)}")
                
    async def _handle_security_alert(self, event):
        """Maneja alertas de seguridad"""
        await self.alert_manager.process_alert(event.data)
        
    async def _handle_access_request(self, event):
        """Maneja solicitudes de acceso"""
        access_point = event.data['access_point']
        for agent in self.agents:
            if isinstance(agent, AccessControlAgent) and agent.point_id == access_point:
                await agent.process_access_request(event.data)
            
    async def _handle_agent_status(self, event):
        """Maneja cambios de estado de los agentes"""
        self.logger.logger.info(
            f"Estado de agente actualizado: {event.data['agent_id']} -> {event.data['status']}"
        )

    def register_agent(self, agent: BaseAgent):
        """Registra un nuevo agente"""
        self.agents.append(agent)

    def process_event(self, event_data):
        """Procesa eventos detectados"""
        
    def handle_alert(self, alert_type, data):
        """Gestiona las alertas del sistema""" 