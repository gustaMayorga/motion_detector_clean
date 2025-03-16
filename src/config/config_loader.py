import os
import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger("ConfigLoader")

def load_config(config_path: str) -> Dict[str, Any]:
    """Carga la configuración desde un archivo YAML y sustituye variables de entorno"""
    if not os.path.exists(config_path):
        logger.error(f"Archivo de configuración no encontrado: {config_path}")
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Procesar variables de entorno en la configuración
        config = _process_env_vars(config)
        
        return config
    except yaml.YAMLError as e:
        logger.error(f"Error al parsear el archivo YAML: {e}")
        raise
    except Exception as e:
        logger.error(f"Error al cargar la configuración: {e}")
        raise

def _process_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """Sustituye variables de entorno en la configuración"""
    if isinstance(config, dict):
        for key, value in config.items():
            config[key] = _process_env_vars(value)
    elif isinstance(config, list):
        for i, item in enumerate(config):
            config[i] = _process_env_vars(item)
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        # Extraer nombre de la variable de entorno
        env_var = config[2:-1]
        # Obtener valor de la variable de entorno o usar string vacío si no existe
        env_value = os.environ.get(env_var, "")
        return env_value
    
    return config

def save_config(config: Dict[str, Any], config_path: str) -> bool:
    """Guarda la configuración en un archivo YAML"""
    try:
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
        
        logger.info(f"Configuración guardada en {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error al guardar la configuración: {e}")
        return False 