import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class EmailNotifier:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger('EmailNotifier')
        
    def send(self, alert_data, recipients):
        """Envía una notificación por correo electrónico"""
        if not recipients:
            self.logger.warning("No recipients specified for email notification")
            return False
            
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.config['from_addr']
            msg['To'] = ', '.join(recipients)
            
            # Definir asunto según tipo de alerta
            alert_type = alert_data.get('type', 'general')
            priority = alert_data.get('priority', 'medium')
            
            # Prefijo según prioridad
            prefix = {
                'high': '[URGENTE] ',
                'medium': '[ALERTA] ',
                'low': '[INFO] '
            }.get(priority, '')
            
            msg['Subject'] = f"{prefix}Alerta de seguridad: {alert_type.capitalize()}"
            
            # Crear cuerpo del mensaje
            body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .alert {{ padding: 10px; border-radius: 5px; margin-bottom: 10px; }}
                    .high {{ background-color: #ffdddd; color: #990000; }}
                    .medium {{ background-color: #ffffcc; color: #996600; }}
                    .low {{ background-color: #e6f3ff; color: #004d99; }}
                    .timestamp {{ font-size: 0.8em; color: #666; }}
                    .location {{ font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="alert {priority}">
                    <h2>{alert_type.capitalize()}</h2>
                    <p>{alert_data.get('message', 'Sin detalles')}</p>
                    <p class="location">Ubicación: {alert_data.get('location', 'Desconocida')}</p>
                    <p class="timestamp">Fecha y hora: {datetime.fromtimestamp(alert_data.get('timestamp', datetime.now().timestamp())).strftime('%d/%m/%Y %H:%M:%S')}</p>
                    
                    {f'<p><a href="{alert_data.get("video_url")}">Ver video</a></p>' if 'video_url' in alert_data else ''}
                    {f'<p><a href="{alert_data.get("image_url")}">Ver imagen</a></p>' if 'image_url' in alert_data else ''}
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Conectar al servidor SMTP
            server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
            server.starttls()
            server.login(self.config['username'], self.config['password'])
            
            # Enviar correo
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Email notification sent to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
            return False 