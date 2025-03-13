import logging
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any, Optional
import asyncio
from logging.handlers import RotatingFileHandler

class SecurityLogger:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_dir = Path(config['log_dir'])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger
        self.logger = logging.getLogger('security_system')
        self.logger.setLevel(logging.INFO)
        
        # Handler para archivo
        log_file = self.log_dir / 'security.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(file_handler)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(console_handler)
        
    async def log_event(self, event_type: str, data: Dict[str, Any]):
        """Registra un evento en el log"""
        event_data = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data
        }
        
        # Guardar en archivo JSON
        events_file = self.log_dir / 'events.json'
        try:
            if events_file.exists():
                with open(events_file) as f:
                    events = json.load(f)
            else:
                events = []
                
            events.append(event_data)
            
            with open(events_file, 'w') as f:
                json.dump(events, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error guardando evento: {e}")
            
        # Registrar en log
        self.logger.info(f"Event: {event_type} - {json.dumps(data)}")
        
    async def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Registra un error en el log"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error),
            'type': type(error).__name__,
            'context': context or {}
        }
        
        # Guardar en archivo JSON
        errors_file = self.log_dir / 'errors.json'
        try:
            if errors_file.exists():
                with open(errors_file) as f:
                    errors = json.load(f)
            else:
                errors = []
                
            errors.append(error_data)
            
            with open(errors_file, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error guardando error: {e}")
            
        # Registrar en log
        self.logger.error(f"Error: {error} - Context: {context}")
            
    def rotate_logs(self):
        """Fuerza la rotación de logs"""
        for handler in self.logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                handler.doRollover() 