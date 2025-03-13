from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os
from pathlib import Path

# Crear directorio de templates si no existe
templates_dir = Path("src/web/templates")
templates_dir.mkdir(parents=True, exist_ok=True)

# Crear directorio de static si no existe
static_dir = Path("src/web/static")
static_dir.mkdir(parents=True, exist_ok=True)

# Inicializar aplicación FastAPI
app = FastAPI(title="Sistema de Videovigilancia - Interfaz Web")

# Configurar cliente HTTP para comunicación con API
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8050")
http_client = httpx.AsyncClient(base_url=API_URL)

# Configurar templates
templates = Jinja2Templates(directory="src/web/templates")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Página principal del dashboard"""
    try:
        # Obtener estado del sistema desde la API
        system_status = await http_client.get("/status")
        system_status.raise_for_status()
        status_data = system_status.json()
        
        # Obtener últimos eventos
        events = await http_client.get("/events", params={"limit": 10})
        events.raise_for_status()
        events_data = events.json()
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "system_status": status_data,
                "events": events_data
            }
        )
    except httpx.HTTPError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Error de comunicación con API: {str(e)}"
            }
        )

@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    """Página de gestión de agentes"""
    try:
        # Obtener lista de agentes
        agents = await http_client.get("/agents")
        agents.raise_for_status()
        agents_data = agents.json()
        
        return templates.TemplateResponse(
            "agents.html",
            {
                "request": request,
                "agents": agents_data
            }
        )
    except httpx.HTTPError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Error de comunicación con API: {str(e)}"
            }
        )

@app.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    event_type: str = None
):
    """Página de historial de eventos"""
    try:
        # Construir parámetros de consulta
        params = {"limit": limit, "offset": offset}
        if event_type:
            params["event_type"] = event_type
            
        # Obtener eventos
        events = await http_client.get("/events", params=params)
        events.raise_for_status()
        events_data = events.json()
        
        return templates.TemplateResponse(
            "events.html",
            {
                "request": request,
                "events": events_data,
                "current_page": offset // limit + 1,
                "total_pages": max(1, (len(events_data) + limit - 1) // limit),
                "event_type": event_type
            }
        )
    except httpx.HTTPError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Error de comunicación con API: {str(e)}"
            }
        )

@app.get("/media", response_class=HTMLResponse)
async def media_page(request: Request):
    """Página de visualización de grabaciones y snapshots"""
    try:
        # Obtener snapshots
        snapshots = await http_client.get("/snapshots", params={"limit": 20})
        snapshots.raise_for_status()
        snapshots_data = snapshots.json()
        
        # Obtener grabaciones
        recordings = await http_client.get("/recordings", params={"limit": 20})
        recordings.raise_for_status()
        recordings_data = recordings.json()
        
        return templates.TemplateResponse(
            "media.html",
            {
                "request": request,
                "snapshots": snapshots_data,
                "recordings": recordings_data
            }
        )
    except httpx.HTTPError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Error de comunicación con API: {str(e)}"
            }
        )

@app.post("/api/agents/{agent_id}/start")
async def start_agent_proxy(agent_id: str):
    """Proxy para iniciar agente"""
    try:
        response = await http_client.post(f"/agents/{agent_id}/start")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code if hasattr(e, 'response') else 500, 
                           detail=str(e))

@app.post("/api/agents/{agent_id}/stop")
async def stop_agent_proxy(agent_id: str):
    """Proxy para detener agente"""
    try:
        response = await http_client.post(f"/agents/{agent_id}/stop")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code if hasattr(e, 'response') else 500, 
                           detail=str(e))

@app.delete("/api/agents/{agent_id}")
async def delete_agent_proxy(agent_id: str):
    """Proxy para eliminar agente"""
    try:
        response = await http_client.delete(f"/agents/{agent_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code if hasattr(e, 'response') else 500, 
                           detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Cierra el cliente HTTP al apagar la aplicación"""
    await http_client.aclose() 