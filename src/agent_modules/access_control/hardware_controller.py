from typing import Dict, Any, Optional
import asyncio
from enum import Enum
import RPi.GPIO as GPIO  # Simularemos si no está en Raspberry Pi

class DeviceStatus(Enum):
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"

class AccessHardwareController:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = {}
        self._setup_gpio()
        
    def _setup_gpio(self):
        """Configura los pines GPIO"""
        try:
            GPIO.setmode(GPIO.BCM)
            
            # Configurar pines para barrera
            GPIO.setup(self.config['pins']['barrier'], GPIO.OUT)
            GPIO.setup(self.config['pins']['sensor'], GPIO.IN)
            
            # Configurar LED de estado
            GPIO.setup(self.config['pins']['status_led'], GPIO.OUT)
            
        except Exception as e:
            print(f"Error setting up GPIO: {e}")
            # Modo simulación si no hay GPIO
            self.simulation_mode = True
            
    async def open_barrier(self, duration: int = 15) -> bool:
        """Abre la barrera por un tiempo determinado"""
        try:
            # Activar relé de barrera
            GPIO.output(self.config['pins']['barrier'], GPIO.HIGH)
            
            # Esperar duración especificada
            await asyncio.sleep(duration)
            
            # Cerrar barrera
            GPIO.output(self.config['pins']['barrier'], GPIO.LOW)
            
            return True
            
        except Exception as e:
            print(f"Error controlling barrier: {e}")
            return False
            
    async def check_sensor(self) -> bool:
        """Verifica el estado del sensor de presencia"""
        try:
            return GPIO.input(self.config['pins']['sensor']) == GPIO.HIGH
        except:
            # Simulación
            return True
            
    def set_status_led(self, status: str):
        """Configura LED de estado"""
        try:
            if status == "ready":
                GPIO.output(self.config['pins']['status_led'], GPIO.HIGH)
            elif status == "error":
                self._blink_led()
            else:
                GPIO.output(self.config['pins']['status_led'], GPIO.LOW)
        except:
            pass
            
    async def _blink_led(self, times: int = 3):
        """Hace parpadear el LED"""
        for _ in range(times):
            GPIO.output(self.config['pins']['status_led'], GPIO.HIGH)
            await asyncio.sleep(0.5)
            GPIO.output(self.config['pins']['status_led'], GPIO.LOW)
            await asyncio.sleep(0.5) 