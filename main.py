import asyncio
from pathlib import Path
from src.core.master_control.system_controller import SystemController
import signal
import sys

async def main():
    # Cargar configuración
    config_path = Path("data/configs/system_config.yaml")
    
    # Inicializar controlador
    controller = SystemController(config_path)
    
    # Manejar señales de terminación
    def signal_handler(sig, frame):
        print("\nDeteniendo sistema...")
        asyncio.create_task(controller.shutdown())
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar sistema
    await controller.start()

if __name__ == "__main__":
    asyncio.run(main()) 