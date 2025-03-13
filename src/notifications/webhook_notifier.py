import logging
import requests
import json

class WebhookNotifier:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('WebhookNotifier')
        
    def send(self, alert_data, recipients=None):
        """Envía una notificación a través de webhook"""
        try:
            url = self.config.get('url')
            method = self.config.get('method', 'POST').upper()
            headers = self.config.get('headers', {"Content-Type": "application/json"})
            
            if not url:
                self.logger.error("Missing webhook URL")
                return False
                
            # Preparar datos a enviar (incluir toda la información de la alerta)
            payload = alert_data.copy()
            
            # Realizar la solicitud HTTP
            if method == 'POST':
                response = requests.post(url, json=payload, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=payload, headers=headers)
            else:
                self.logger.error(f"Unsupported webhook method: {method}")
                return False
                
            # Verificar respuesta
            if response.status_code >= 200 and response.status_code < 300:
                self.logger.info(f"Webhook notification sent successfully: {response.status_code}")
                return True
            else:
                self.logger.error(f"Webhook error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in webhook notification: {e}")
            return False 