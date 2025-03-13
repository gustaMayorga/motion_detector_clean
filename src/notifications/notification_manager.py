import json
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time
from threading import Thread, Lock
from queue import Queue, PriorityQueue

class NotificationManager:
    def __init__(self, config_path="configs/notifications.json"):
        self.config = self._load_config(config_path)
        self.channels = self._init_channels()
        self.logger = logging.getLogger('NotificationManager')
        self.notification_queue = PriorityQueue()
        self.queue_lock = Lock()
        self.processing_thread = Thread(target=self._process_notification_queue, daemon=True)
        self.processing_thread.start()
        self.rate_limiters = {}  # Para limitar frecuencia de notificaciones
        
    def _load_config(self, config_path):
        """Cargar configuración de notificaciones desde archivo JSON"""
        if not os.path.exists(config_path):
            self.logger.warning(f"Config file {config_path} not found, using defaults")
            return {
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "from_addr": ""
                },
                "sms": {
                    "enabled": False,
                    "provider": "twilio",
                    "account_sid": "",
                    "auth_token": "",
                    "from_number": ""
                },
                "push": {
                    "enabled": False,
                    "provider": "firebase",
                    "api_key": ""
                },
                "webhook": {
                    "enabled": True,
                    "url": "http://localhost:8000/api/notifications",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"}
                },
                "recipients": {
                    "high_priority": {
                        "email": ["security@example.com"],
                        "sms": ["+1234567890"],
                        "push": ["device_token_1"]
                    },
                    "medium_priority": {
                        "email": ["manager@example.com"],
                        "push": ["device_token_2"]
                    },
                    "low_priority": {
                        "email": ["logs@example.com"]
                    }
                },
                "priority_channels": {
                    "high": ["sms", "push", "webhook", "email"],
                    "medium": ["push", "webhook", "email"],
                    "low": ["webhook", "email"]
                },
                "rate_limits": {
                    "high": 60,    # Segundos entre notificaciones
                    "medium": 300,
                    "low": 1800
                }
            }
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading notification config: {e}")
            return {}
            
    def _init_channels(self):
        """Inicializar canales de notificación configurados"""
        channels = {}
        
        if self.config.get('email', {}).get('enabled', False):
            channels['email'] = EmailNotifier(self.config['email'])
            
        if self.config.get('sms', {}).get('enabled', False):
            channels['sms'] = SMSNotifier(self.config['sms'])
            
        if self.config.get('push', {}).get('enabled', False):
            channels['push'] = PushNotifier(self.config['push'])
            
        if self.config.get('webhook', {}).get('enabled', False):
            channels['webhook'] = WebhookNotifier(self.config['webhook'])
            
        return channels
        
    def _get_recipients_for_priority(self, priority):
        """Obtener destinatarios según prioridad"""
        priority_map = {
            "high": "high_priority",
            "medium": "medium_priority",
            "low": "low_priority"
        }
        
        priority_key = priority_map.get(priority, "low_priority")
        return self.config.get("recipients", {}).get(priority_key, {})
        
    def _get_channels_for_priority(self, priority):
        """Obtener canales de notificación según prioridad"""
        return self.config.get("priority_channels", {}).get(priority, ["email"])
        
    def _can_send_notification(self, alert_key, priority):
        """Verificar si podemos enviar una notificación según límites de frecuencia"""
        if alert_key not in self.rate_limiters:
            self.rate_limiters[alert_key] = 0
            return True
            
        last_sent = self.rate_limiters[alert_key]
        rate_limit = self.config.get("rate_limits", {}).get(priority, 300)  # Default 5 minutos
        
        current_time = time.time()
        if current_time - last_sent >= rate_limit:
            return True
            
        return False
        
    def send_alert(self, alert_data, channel_types=None, priority="medium"):
        """Enviar alerta por los canales especificados según prioridad"""
        # Verificar datos mínimos
        if not isinstance(alert_data, dict) or 'message' not in alert_data:
            self.logger.error("Invalid alert data format")
            return False
            
        # Obtener canales basados en prioridad si no se especifican
        if channel_types is None:
            channel_types = self._get_channels_for_priority(priority)
            
        # Obtener destinatarios para esta prioridad
        recipients = self._get_recipients_for_priority(priority)
        
        # Agregar información de prioridad y timestamp
        if 'timestamp' not in alert_data:
            alert_data['timestamp'] = time.time()
        alert_data['priority'] = priority
        
        # Generar clave única para control de frecuencia
        alert_key = f"{alert_data.get('type', 'generic')}_{alert_data.get('location', 'unknown')}"
        
        # Verificar límites de frecuencia
        if not self._can_send_notification(alert_key, priority):
            self.logger.info(f"Rate limited notification: {alert_key}")
            return False
            
        # Actualizar timestamp de última notificación
        self.rate_limiters[alert_key] = time.time()
        
        # Agregar a la cola de notificaciones con prioridad
        priority_value = {"high": 0, "medium": 1, "low": 2}.get(priority, 1)
        
        with self.queue_lock:
            self.notification_queue.put((
                priority_value, 
                {
                    "data": alert_data,
                    "channels": channel_types,
                    "recipients": recipients
                }
            ))
            
        return True
        
    def _process_notification_queue(self):
        """Procesar cola de notificaciones en segundo plano"""
        while True:
            try:
                # Obtener notificación de mayor prioridad
                priority, notification = self.notification_queue.get()
                
                alert_data = notification["data"]
                channels = notification["channels"]
                recipients = notification["recipients"]
                
                # Procesar cada canal configurado
                for channel_type in channels:
                    if channel_type not in self.channels:
                        self.logger.warning(f"Channel {channel_type} not available")
                        continue
                        
                    channel = self.channels[channel_type]
                    channel_recipients = recipients.get(channel_type, [])
                    
                    if not channel_recipients and channel_type != 'webhook':
                        self.logger.warning(f"No recipients configured for {channel_type}")
                        continue
                        
                    try:
                        # Enviar notificación
                        channel.send(alert_data, channel_recipients)
                    except Exception as e:
                        self.logger.error(f"Error sending {channel_type} notification: {e}")
                        
                self.notification_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in notification queue processing: {e}")
                time.sleep(1)  # Evitar bucle 