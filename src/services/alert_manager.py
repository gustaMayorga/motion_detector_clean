from typing import Dict, List, Any
import asyncio
from datetime import datetime
import json
from pathlib import Path
import aiohttp

class AlertManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alert_history = []
        self.notification_channels = {
            'whatsapp': self._send_whatsapp_alert,
            'email': self._send_email_alert,
            'push': self._send_push_notification,
            'monitoring': self._notify_monitoring_station
        }
        
    async def process_alert(self, alert_data: Dict[str, Any]):
        """Procesa y distribuye una alerta"""
        alert_id = self._generate_alert_id()
        alert = {
            'alert_id': alert_id,
            'timestamp': datetime.now().isoformat(),
            'data': alert_data,
            'status': 'new'
        }
        
        # Guardar alerta
        self.alert_history.append(alert)
        self._save_alert_to_disk(alert)
        
        # Determinar canales de notificación basado en severidad
        channels = self._determine_notification_channels(alert_data['severity'])
        
        # Enviar notificaciones
        notification_tasks = [
            self.notification_channels[channel](alert)
            for channel in channels
        ]
        
        await asyncio.gather(*notification_tasks)
        
    async def _send_whatsapp_alert(self, alert: Dict[str, Any]):
        """Envía alerta por WhatsApp"""
        try:
            message = self._format_whatsapp_message(alert)
            # Implementar lógica de envío de WhatsApp
            pass
        except Exception as e:
            print(f"Error enviando WhatsApp: {e}")
            
    def _determine_notification_channels(self, severity: int) -> List[str]:
        """Determina qué canales usar basado en la severidad"""
        if severity >= 4:
            return ['whatsapp', 'push', 'monitoring']
        elif severity >= 3:
            return ['whatsapp', 'push']
        else:
            return ['push']
            
    def _save_alert_to_disk(self, alert: Dict[str, Any]):
        """Guarda la alerta en disco"""
        alerts_dir = Path('data/alerts')
        alerts_dir.mkdir(exist_ok=True)
        
        file_path = alerts_dir / f"alert_{alert['alert_id']}.json"
        with open(file_path, 'w') as f:
            json.dump(alert, f, indent=2) 