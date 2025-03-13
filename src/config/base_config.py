from typing import Dict, Any, Optional
import yaml
from pathlib import Path
from dataclasses import dataclass

@dataclass
class AgentConfig:
    agent_type: str
    name: str
    enabled: bool
    settings: Dict[str, Any]

class ConfigManager:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config_dir = config_path.parent
        self.system_config = self._load_config(config_path)
        self.agent_configs = {}
        self._load_agent_configs()
        
    def _load_config(self, path: Path) -> Dict[str, Any]:
        """Carga un archivo de configuración YAML"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Error cargando configuración {path}: {e}")
            
    def _load_agent_configs(self):
        """Carga las configuraciones de todos los agentes"""
        agent_types = ['video', 'access']
        
        for agent_type in agent_types:
            config_file = self.config_dir / f"{agent_type}_agent_config.yaml"
            if config_file.exists():
                config_data = self._load_config(config_file)
                self.agent_configs[agent_type] = config_data
                
    def get_system_config(self) -> Dict[str, Any]:
        """Retorna la configuración del sistema"""
        return self.system_config
        
    def get_agent_config(self, agent_type: str) -> AgentConfig:
        """Obtiene la configuración de un tipo de agente"""
        if agent_type not in self.agent_configs:
            raise ValueError(f"Configuración no encontrada para agente: {agent_type}")
            
        config_data = self.agent_configs[agent_type]
        return AgentConfig(
            agent_type=agent_type,
            name=config_data.get('name', f"{agent_type}_agent"),
            enabled=config_data.get('enabled', True),
            settings=config_data.get('settings', {})
        )
        
    def update_agent_config(self, agent_type: str, settings: Dict[str, Any]):
        """Actualiza la configuración de un agente"""
        if agent_type not in self.agent_configs:
            raise ValueError(f"Agente no encontrado: {agent_type}")
            
        # Actualizar configuración en memoria
        self.agent_configs[agent_type]['settings'].update(settings)
        
        # Guardar en disco
        config_file = self.config_dir / f"{agent_type}_agent_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(self.agent_configs[agent_type], f)

    def get_ml_config(self) -> Dict[str, Any]:
        """Obtiene configuración del motor ML"""
        return self.system_config.get('ml_engine', {}) 