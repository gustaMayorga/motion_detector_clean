import logging
import requests
from datetime import datetime

class SMSNotifier:
    def __init__(self, config):
        self.config = config
        self.provider = config.get('provider', 'twilio')
        self.logger = logging.getLogger('SMSNotifier')
        
    def send(self, alert_data, recipients):
        """Envía una notificación por SMS"""
        if not recipients:
            self.logger.warning("No recipients specified for SMS notification")
            return False
            
        if self.provider == 'twilio':
            return self._send_twilio(alert_data, recipients)
        else:
            self.logger.error(f"Unsupported SMS provider: {self.provider}")
            return False
            
    def _send_twilio(self, alert_data, recipients):
        """Envía SMS usando Twilio API"""
        try:
            from twilio.rest import Client
            
            account_sid = self.config.get('account_sid')
            auth_token = self.config.get('auth_token')
            from_number = self.config.get('from_number')
            
            if not all([account_sid, auth_token, from_number]):
                self.logger.error("Missing Twilio configuration")
                return False
                
            client = Client(account_sid, auth_token)
            
            # Formatear mensaje
            alert_type = alert_data.get('type', 'general')
            priority = alert_data.get('priority', 'medium')
            location = alert_data.get('location', 'Desconocida')
            
            # Prefijo según prioridad
            prefix = {
                'high': '🚨 URGENTE: ',
                'medium': '⚠️ ALERTA: ',
                'low': 'INFO: '
            }.get(priority, '')
            
            message_body = f"{prefix}{alert_type.upper()}\n{alert_data.get('message', 'Sin detalles')}\nUbicación: {location}"
            
            # Agregar timestamp
            timestamp = datetime.fromtimestamp(alert_data.get('timestamp', datetime.now().timestamp()))
            message_body += f"\nFecha/Hora: {timestamp.strftime('%d/%m/%Y %H:%M')}"
            
            # Enviar a cada destinatario
            success_count = 0
            for recipient in recipients:
                try:
                    message = client.messages.create(
                        body=message_body,
                        from_=from_number,
                        to=recipient
                    )
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"Error sending SMS to {recipient}: {e}")
            
            self.logger.info(f"SMS notification sent to {success_count}/{len(recipients)} recipients")
            return success_count > 0
            
        except ImportError:
            self.logger.error("Twilio package not installed. Install with: pip install twilio")
            return False
        except Exception as e:
            self.logger.error(f"Error in Twilio SMS notification: {e}")
            return False 