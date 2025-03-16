import jwt
from fastapi import Depends, HTTPException, status, WebSocket
from typing import Optional

# Variables para configuración
SECRET_KEY = "tu_clave_secreta_para_pruebas"  # Cambia esto en producción
ALGORITHM = "HS256"

async def get_current_user_ws(websocket: WebSocket) -> Optional[dict]:
    """
    Función simplificada para autenticación en WebSockets
    Para pruebas, siempre devuelve un usuario de prueba
    """
    # En modo prueba, devolvemos un usuario ficticio
    return {
        "id": 1,
        "username": "test_user",
        "email": "test@example.com",
        "role_id": 1
    } 