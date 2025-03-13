from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class AgentConfigBase:
    name: str
    type: str
    enabled: bool = True
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    settings: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Valida la configuración básica"""
        return all([
            isinstance(self.name, str) and len(self.name) > 0,
            isinstance(self.type, str) and len(self.type) > 0,
            isinstance(self.enabled, bool),
            isinstance(self.settings, dict)
        ])
        
    def update_settings(self, new_settings: Dict[str, Any]):
        """Actualiza la configuración"""
        self.settings.update(new_settings)
        self.updated_at = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario"""
        return {
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "settings": self.settings,
            "dependencies": self.dependencies,
            "metadata": self.metadata
        } 