import logging
import requests
import json

class PushNotifier:
    def __init__(self, config):
        self.config = config
        self.provider = config.get('provider', 'firebase')
        self.logger = logging.getLogger('PushNotifier')
        
    def send(self, alert_data, recipients):
        """Envía una notificación push"""
        if not recipients:
            self.logger.warning("No recipients specified for push notification")
            return False
            
        if self.provider == 'firebase':
            return self._send_firebase(alert_data, recipients)
        else:
            self.logger.error(f"Unsupported push provider: {self.provider}")
            return False
            
    def _send_firebase(self, alert_data, recipients):
        """Envía notificación push usando Firebase Cloud Messaging"""
        try:
            api_key = self.config.get('api_key')
            
            if not api_key:
                self.logger.error("Missing Firebase API key")
                return False
                
            # Formatear mensaje
            alert_type = alert_data.get('type', 'general')
            priority = alert_data.get('priority', 'medium')
            
            # Título según prioridad
            prefix = {
                'high': '🚨 URGENTE: ',
                'medium': '⚠️ ALERTA: ',
                'low': 'INFO: '
            }.get(priority, '')
            
            notification = {
                'title': f"{prefix}{alert_type.capitalize()}",
                'body': alert_data.get('message', 'Sin detalles'),
                'icon': 'notification_icon',
                'sound': 'default',
                'click_action': 'OPEN_ALERT_ACTIVITY'
            }
            
            # Datos adicionales para la app
            data = {
                'type': alert_type,
                'priority': priority,
                'location': alert_data.get('location', 'unknown'),
                'timestamp': str(alert_data.get('timestamp', 0)),
            }
            
            # Agregar URLs si existen
            if 'image_url' in alert_data:
                data['image_url'] = alert_data['image_url']
            if 'video_url' in alert_data:
                data['video_url'] = alert_data['video_url']
                
            # URL de Firebase
            url = 'https://fcm.googleapis.com/fcm/send'
            
            headers = {
                'Authorization': f'key={api_key}',
                'Content-Type': 'application/json'
            }
            
            # Enviar a cada token de dispositivo
            success_count = 0
            for token in recipients:
                payload = {
                    'notification': notification,
                    'data': data,
                    'to': token
                }
                
                try:
                    response = requests.post(url, headers=headers, data=json.dumps(payload))
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('success') == 1:
                            success_count += 1
                        else:
                            self.logger.warning(f"Firebase error for token {token}: {result}")
                    else:
                        self.logger.error(f"Firebase API error: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    self.logger.error(f"Error sending push to {token}: {e}")
            
            self.logger.info(f"Push notification sent to {success_count}/{len(recipients)} devices")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error in Firebase push notification: {e}")
            return False 