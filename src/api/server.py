from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
from pathlib import Path
import asyncio
import logging
from pydantic import BaseModel

# Modelos
from src.core.ml_engine.object_detection import Detection
from src.core.ml_engine.object_tracking import Track
from src.core.ml_engine.behavior_analyzer import BehaviorPattern
from src.core.event_system import Event, EventBus
from src.agent_modules.video_analytics import VideoAnalyticsAgent
from src.agent_modules.base import AgentConfig
from src.utils.logging import SecurityLogger

# Modelos de datos para la API
class EventData(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    priority: int
    data: Dict[str, Any]

class AgentStatus(BaseModel):
    agent_id: str
    agent_type: str
    status: str
    uptime: Optional[float] = None
    last_event: Optional[str] = None
    events_processed: int = 0
    config: Dict[str, Any]

class SystemStatus(BaseModel):
    status: str
    version: str
    agents: List[AgentStatus]
    total_events: int

# Configuración de la aplicación
app = FastAPI(
    title="Sistema de Videovigilancia Inteligente",
    description="API para el sistema de análisis de video con inteligencia artificial",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, específica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado del sistema
system_state = {
    "agents": {},
    "event_bus": None,
    "logger": None,
    "events": [],
    "max_events": 1000,  # Máximo de eventos a almacenar en memoria
}

# Configuración
config_path = os.environ.get("CONFIG_PATH", "config/system_config.json")

# Inicialización del sistema
@app.on_event("startup")
async def startup_event():
    # Configurar logger
    system_state["logger"] = SecurityLogger({"log_dir": "logs"})
    
    # Configurar event bus
    system_state["event_bus"] = EventBus()
    
    # Suscribirse a eventos
    system_state["event_bus"].subscribe("*", store_event)
    
    # Cargar configuración
    # TODO: Implementar carga de configuración desde archivo

async def store_event(event: Event):
    """Almacena eventos en memoria para consulta a través de la API"""
    system_state["events"].append(event)
    # Limitar la cantidad de eventos almacenados
    if len(system_state["events"]) > system_state["max_events"]:
        system_state["events"] = system_state["events"][-system_state["max_events"]:]

# Rutas de la API
@app.get("/", response_model=Dict[str, str])
async def root():
    """Punto de entrada principal de la API"""
    return {
        "name": "Sistema de Videovigilancia Inteligente",
        "version": "1.0.0",
        "status": "online"
    }

@app.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Obtiene el estado actual del sistema"""
    agent_statuses = []
    
    for agent_id, agent in system_state["agents"].items():
        status = "running" if agent.running else "stopped"
        uptime = None
        if hasattr(agent, "start_time") and agent.start_time:
            uptime = (datetime.now() - agent.start_time).total_seconds()
            
        agent_statuses.append(AgentStatus(
            agent_id=agent_id,
            agent_type=agent.__class__.__name__,
            status=status,
            uptime=uptime,
            events_processed=getattr(agent, "events_processed", 0),
            config=agent.config
        ))
    
    return SystemStatus(
        status="online",
        version="1.0.0",
        agents=agent_statuses,
        total_events=len(system_state["events"])
    )

@app.get("/agents", response_model=List[AgentStatus])
async def get_agents():
    """Obtiene la lista de agentes registrados"""
    agent_statuses = []
    
    for agent_id, agent in system_state["agents"].items():
        status = "running" if agent.running else "stopped"
        uptime = None
        if hasattr(agent, "start_time") and agent.start_time:
            uptime = (datetime.now() - agent.start_time).total_seconds()
            
        agent_statuses.append(AgentStatus(
            agent_id=agent_id,
            agent_type=agent.__class__.__name__,
            status=status,
            uptime=uptime,
            events_processed=getattr(agent, "events_processed", 0),
            config=agent.config
        ))
    
    return agent_statuses

@app.post("/agents/video", response_model=Dict[str, str])
async def create_video_agent(
    background_tasks: BackgroundTasks,
    agent_id: str,
    video_source: str,
    camera_id: Optional[str] = None,
    confidence_threshold: float = 0.5
):
    """Crea un nuevo agente de análisis de video"""
    if agent_id in system_state["agents"]:
        raise HTTPException(status_code=400, detail=f"Agente con ID {agent_id} ya existe")
        
    # Configuración básica
    config = {
        "agent_id": agent_id,
        "video_source": video_source,
        "camera_id": camera_id or agent_id,
        "object_detection": {
            "model_path": "models/yolov5s.pt",
            "confidence_threshold": confidence_threshold,
            "device": "cpu"
        },
        "object_tracking": {
            "max_age": 30,
            "min_hits": 3,
            "iou_threshold": 0.3
        },
        "behavior_analysis": {
            "max_history_seconds": 30,
            "loitering_area_threshold": 5000,
            "group_distance_threshold": 100
        },
        "snapshots_dir": "data/snapshots",
        "recording": {
            "enabled": True,
            "storage_path": "data/recordings",
            "fps": 15,
            "max_duration_minutes": 10
        }
    }
    
    # Crear agente
    agent = VideoAnalyticsAgent(
        config=config,
        event_bus=system_state["event_bus"],
        logger=system_state["logger"]
    )
    
    # Registrar agente
    system_state["agents"][agent_id] = agent
    
    # Iniciar en segundo plano
    background_tasks.add_task(agent.start)
    
    return {"status": "success", "message": f"Agente {agent_id} creado y en proceso de inicialización"}

@app.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str, background_tasks: BackgroundTasks):
    """Inicia un agente existente"""
    if agent_id not in system_state["agents"]:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} no encontrado")
        
    agent = system_state["agents"][agent_id]
    
    if agent.running:
        return {"status": "warning", "message": f"Agente {agent_id} ya está en ejecución"}
        
    background_tasks.add_task(agent.start)
    
    return {"status": "success", "message": f"Agente {agent_id} iniciado"}

@app.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Detiene un agente en ejecución"""
    if agent_id not in system_state["agents"]:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} no encontrado")
        
    agent = system_state["agents"][agent_id]
    
    if not agent.running:
        return {"status": "warning", "message": f"Agente {agent_id} ya está detenido"}
        
    await agent.stop()
    
    return {"status": "success", "message": f"Agente {agent_id} detenido"}

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Elimina un agente"""
    if agent_id not in system_state["agents"]:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} no encontrado")
        
    agent = system_state["agents"][agent_id]
    
    # Detener si está en ejecución
    if agent.running:
        await agent.stop()
        
    # Eliminar de registro
    del system_state["agents"][agent_id]
    
    return {"status": "success", "message": f"Agente {agent_id} eliminado"}

@app.get("/events", response_model=List[EventData])
async def get_events(
    limit: int = Query(50, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    min_priority: Optional[int] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None
):
    """Obtiene el historial de eventos con filtros opcionales"""
    events = system_state["events"]
    
    # Aplicar filtros
    if event_type:
        events = [e for e in events if e.event_type == event_type]
        
    if min_priority is not None:
        events = [e for e in events if e.priority >= min_priority]
        
    if from_time:
        from_dt = datetime.fromisoformat(from_time)
        events = [e for e in events if datetime.fromisoformat(e.timestamp) >= from_dt]
        
    if to_time:
        to_dt = datetime.fromisoformat(to_time)
        events = [e for e in events if datetime.fromisoformat(e.timestamp) <= to_dt]
    
    # Paginación
    total = len(events)
    events = events[offset:offset + limit]
    
    # Convertir a formato de respuesta
    result = []
    for event in events:
        result.append(EventData(
            event_id=event.id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            priority=event.priority,
            data=event.data
        ))
    
    return result

@app.get("/snapshots")
async def get_snapshots(
    limit: int = Query(50, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    pattern_type: Optional[str] = None
):
    """Obtiene la lista de snapshots disponibles"""
    snapshots_dir = Path("data/snapshots")
    if not snapshots_dir.exists():
        return []
        
    # Listar archivos
    files = list(snapshots_dir.glob("*.jpg"))
    
    # Filtrar por tipo si se especifica
    if pattern_type:
        files = [f for f in files if pattern_type in f.stem]
        
    # Ordenar por fecha (más reciente primero)
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Paginación
    files = files[offset:offset + limit]
    
    # Construir resultado
    result = []
    for file in files:
        stat = file.stat()
        result.append({
            "filename": file.name,
            "path": str(file),
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "url": f"/snapshots/{file.name}"
        })
    
    return result

@app.get("/snapshots/{filename}")
async def get_snapshot(filename: str):
    """Descarga un snapshot específico"""
    file_path = Path(f"data/snapshots/{filename}")
    
    if not file_path.exists() or file_path.suffix != ".jpg":
        raise HTTPException(status_code=404, detail="Snapshot no encontrado")
        
    return FileResponse(file_path)

@app.get("/recordings")
async def get_recordings(
    limit: int = Query(50, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    camera_id: Optional[str] = None
):
    """Obtiene la lista de grabaciones disponibles"""
    recordings_dir = Path("data/recordings")
    if not recordings_dir.exists():
        return []
        
    # Listar archivos
    files = list(recordings_dir.glob("*.mp4"))
    
    # Filtrar por cámara si se especifica
    if camera_id:
        files = [f for f in files if camera_id in f.stem]
        
    # Ordenar por fecha (más reciente primero)
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Paginación
    files = files[offset:offset + limit]
    
    # Construir resultado
    result = []
    for file in files:
        stat = file.stat()
        
        # Intentar cargar metadatos
        metadata = {}
        metadata_path = file.with_name(f"{file.stem}_metadata.json")
        if metadata_path.exists():
            try:
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            except:
                pass
                
        result.append({
            "filename": file.name,
            "path": str(file),
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "url": f"/recordings/{file.name}",
            "metadata": metadata
        })
    
    return result

@app.get("/recordings/{filename}")
async def get_recording(filename: str):
    """Descarga una grabación específica"""
    file_path = Path(f"data/recordings/{filename}")
    
    if not file_path.exists() or file_path.suffix != ".mp4":
        raise HTTPException(status_code=404, detail="Grabación no encontrada")
        
    return FileResponse(file_path)

# Ejecutar la aplicación
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 