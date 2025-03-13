from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid
from dataclasses import dataclass
import json
from pathlib import Path

@dataclass
class VisitorPass:
    visitor_id: str
    host_id: str
    name: str
    document_id: str
    valid_from: datetime
    valid_until: datetime
    access_points: List[str]
    vehicle_plate: Optional[str] = None
    face_id: Optional[str] = None
    status: str = "active"

class VisitorManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_passes: Dict[str, VisitorPass] = {}
        self.pass_history: List[Dict[str, Any]] = []
        self.storage_path = Path(config['storage_path'])
        self._load_passes()
        
    async def create_visitor_pass(self, visitor_data: Dict[str, Any]) -> VisitorPass:
        """Crea un nuevo pase de visitante"""
        visitor_id = str(uuid.uuid4())
        
        # Crear pase
        pass_data = VisitorPass(
            visitor_id=visitor_id,
            host_id=visitor_data['host_id'],
            name=visitor_data['name'],
            document_id=visitor_data['document_id'],
            valid_from=datetime.fromisoformat(visitor_data['valid_from']),
            valid_until=datetime.fromisoformat(visitor_data['valid_until']),
            access_points=visitor_data.get('access_points', ['main']),
            vehicle_plate=visitor_data.get('vehicle_plate'),
            face_id=visitor_data.get('face_id')
        )
        
        # Guardar pase
        self.active_passes[visitor_id] = pass_data
        await self._save_passes()
        
        return pass_data
        
    async def validate_pass(self, visitor_id: str, access_point: str) -> bool:
        """Valida un pase de visitante"""
        if visitor_id not in self.active_passes:
            return False
            
        pass_data = self.active_passes[visitor_id]
        now = datetime.now()
        
        # Verificar validez temporal
        if not (pass_data.valid_from <= now <= pass_data.valid_until):
            await self._expire_pass(visitor_id)
            return False
            
        # Verificar punto de acceso
        if access_point not in pass_data.access_points:
            return False
            
        return pass_data.status == "active"
        
    async def _expire_pass(self, visitor_id: str):
        """Expira un pase de visitante"""
        if visitor_id in self.active_passes:
            pass_data = self.active_passes[visitor_id]
            pass_data.status = "expired"
            
            # Mover a historial
            self.pass_history.append({
                "pass_data": pass_data.__dict__,
                "expiry_date": datetime.now().isoformat()
            })
            
            del self.active_passes[visitor_id]
            await self._save_passes()
            
    async def _save_passes(self):
        """Guarda los pases en disco"""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            
            # Guardar pases activos
            active_file = self.storage_path / "active_passes.json"
            with open(active_file, 'w') as f:
                json.dump(
                    {k: v.__dict__ for k, v in self.active_passes.items()},
                    f,
                    default=str
                )
                
            # Guardar historial
            history_file = self.storage_path / "pass_history.json"
            with open(history_file, 'w') as f:
                json.dump(self.pass_history, f, default=str)
                
        except Exception as e:
            print(f"Error guardando pases: {e}") 