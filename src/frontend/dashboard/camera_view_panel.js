/**
 * Panel de Visualización de Cámaras
 * 
 * Gestiona la visualización y control de múltiples cámaras de seguridad.
 */
class CameraViewPanel {
    /**
     * Inicializa el panel de cámaras
     * @param {string} containerId ID del contenedor HTML
     * @param {string} apiEndpoint Endpoint de la API para cámaras
     */
    constructor(containerId, apiEndpoint) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with ID ${containerId} not found`);
            return;
        }
        
        this.apiEndpoint = apiEndpoint;
        this.cameras = new Map();
        this.activeStreams = new Map();
        this.selectedCamera = null;
        this.layout = '2x2';  // Opciones: '1x1', '2x2', '3x3', 'custom'
        this.eventListeners = {
            cameraSelected: []
        };
        
        this.initialize();
    }
    
    /**
     * Inicializar componentes de la UI
     */
    initialize() {
        // Crear estructura básica si no existe
        if (!document.getElementById('camera-grid')) {
            this.container.innerHTML = `
                <div class="camera-controls d-flex justify-content-between mb-3">
                    <div class="layout-controls btn-group">
                        <button class="btn btn-outline-secondary layout-btn" data-layout="1x1">
                            <i class="fas fa-square"></i>
                        </button>
                        <button class="btn btn-outline-secondary layout-btn active" data-layout="2x2">
                            <i class="fas fa-th-large"></i>
                        </button>
                        <button class="btn btn-outline-secondary layout-btn" data-layout="3x3">
                            <i class="fas fa-th"></i>
                        </button>
                    </div>
                    <div class="camera-actions">
                        <select id="camera-selector" class="custom-select">
                            <option value="">Seleccionar cámara...</option>
                        </select>
                        <button id="refresh-cameras" class="btn btn-primary ml-2">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    </div>
                </div>
                <div id="camera-grid" class="camera-grid grid-2x2">
                    <div class="camera-placeholder text-center p-5">
                        <i class="fas fa-video fa-3x mb-3"></i>
                        <p>No hay cámaras disponibles</p>
                    </div>
                </div>
                <div id="camera-detail-panel" class="camera-detail d-none">
                    <div class="detail-header d-flex justify-content-between">
                        <h3 id="camera-detail-title">Detalles de la Cámara</h3>
                        <button id="close-camera-detail" class="btn btn-sm btn-light">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div id="camera-details-content"></div>
                </div>
            `;
            
            // Configurar event listeners
            this.setupEventListeners();
        }
        
        // Cargar cámaras iniciales
        this.loadCameras();
    }
    
    /**
     * Configurar event listeners para controles de la UI
     */
    setupEventListeners() {
        // Botones de layout
        const layoutButtons = document.querySelectorAll('.layout-btn');
        layoutButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Actualizar clase activa
                layoutButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Cambiar layout
                const layout = button.getAttribute('data-layout');
                this.changeLayout(layout);
            });
        });
        
        // Selector de cámara
        const cameraSelector = document.getElementById('camera-selector');
        if (cameraSelector) {
            cameraSelector.addEventListener('change', () => {
                const cameraId = cameraSelector.value;
                if (cameraId) {
                    this.focusCamera(cameraId);
                }
            });
        }
        
        // Botón de actualizar
        const refreshBtn = document.getElementById('refresh-cameras');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadCameras();
            });
        }
        
        // Cerrar detalles de cámara
        const closeDetailBtn = document.getElementById('close-camera-detail');
        if (closeDetailBtn) {
            closeDetailBtn.addEventListener('click', () => {
                this.hideCameraDetails();
            });
        }
    }
    
    /**
     * Cargar lista de cámaras desde la API
     */
    loadCameras() {
        const cameraGrid = document.getElementById('camera-grid');
        if (cameraGrid) {
            cameraGrid.innerHTML = `
                <div class="loading-indicator text-center p-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="sr-only">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando cámaras...</p>
                </div>
            `;
        }
        
        fetch(this.apiEndpoint)
            .then(response => response.json())
            .then(data => {
                // Almacenar cámaras
                this.cameras.clear();
                data.forEach(camera => {
                    this.cameras.set(camera.id, camera);
                });
                
                // Actualizar selector
                this.updateCameraSelector();
                
                // Renderizar grid
                this.renderCameraGrid();
            })
            .catch(error => {
                console.error('Error loading cameras:', error);
                // Mostrar mensaje de error
                const cameraGrid = document.getElementById('camera-grid');
                if (cameraGrid) {
                    cameraGrid.innerHTML = `
                        <div class="alert alert-danger m-3">
                            Error al cargar cámaras. Por favor, intente nuevamente.
                        </div>
                    `;
                }
            });
    }
    
    /**
     * Actualizar selector de cámaras
     */
    updateCameraSelector() {
        const selector = document.getElementById('camera-selector');
        if (!selector) return;
        
        // Guardar selección actual
        const currentSelection = selector.value;
        
        // Limpiar opciones existentes, manteniendo la primera
        while (selector.options.length > 1) {
            selector.remove(1);
        }
        
        // Agregar opciones de cámaras
        this.cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.id;
            option.textContent = camera.name;
            selector.appendChild(option);
        });
        
        // Restaurar selección si existe
        if (currentSelection && Array.from(this.cameras.keys()).includes(currentSelection)) {
            selector.value = currentSelection;
        }
    }
    
    /**
     * Cambiar layout de la cuadrícula
     */
    changeLayout(layout) {
        this.layout = layout;
        
        const grid = document.getElementById('camera-grid');
        if (!grid) return;
        
        // Quitar clases existentes
        grid.classList.remove('grid-1x1', 'grid-2x2', 'grid-3x3', 'grid-custom');
        
        // Agregar nueva clase
        grid.classList.add(`grid-${layout}`);
        
        // Renderizar cámaras con nuevo layout
        this.renderCameraGrid();
    }
    
    /**
     * Renderizar cuadrícula de cámaras
     */
    renderCameraGrid() {
        const grid = document.getElementById('camera-grid');
        if (!grid) return;
        
        // Determinar cuántas cámaras mostrar según layout
        let camCount;
        switch (this.layout) {
            case '1x1': camCount = 1; break;
            case '2x2': camCount = 4; break;
            case '3x3': camCount = 9; break;
            case 'custom': camCount = 6; break;
            default: camCount = 4;
        }
        
        // Comprobar si hay cámaras
        if (this.cameras.size === 0) {
            grid.innerHTML = `
                <div class="camera-placeholder text-center p-5">
                    <i class="fas fa-video-slash fa-3x mb-3"></i>
                    <p>No hay cámaras disponibles</p>
                </div>
            `;
            return;
        }
        
        // Limpiar grid
        grid.innerHTML = '';
        
        // Detener streams activos
        this.stopAllStreams();
        
        // Seleccionar cámaras a mostrar
        let camerasToShow;
        if (this.selectedCamera && this.layout === '1x1') {
            // En vista de una sola cámara, mostrar la seleccionada
            camerasToShow = [this.cameras.get(this.selectedCamera)];
        } else {
            // En otros layouts, mostrar las primeras N cámaras
            camerasToShow = Array.from(this.cameras.values()).slice(0, camCount);
        }
        
        // Crear elementos para cada cámara
        camerasToShow.forEach(camera => {
            const cameraElement = document.createElement('div');
            cameraElement.className = 'camera-cell';
            cameraElement.id = `camera-cell-${camera.id}`;
            
            cameraElement.innerHTML = `
                <div class="camera-header">
                    <span class="camera-name">${camera.name}</span>
                    <span class="camera-status ${camera.status === 'online' ? 'online' : 'offline'}">
                        ${camera.status === 'online' ? 'EN LÍNEA' : 'FUERA DE LÍNEA'}
                    </span>
                </div>
                <div class="camera-stream" id="stream-${camera.id}">
                    ${camera.status === 'online' 
                        ? '<div class="loading-stream"><span class="spinner-border spinner-border-sm"></span> Cargando feed...</div>'
                        : '<div class="offline-message">Cámara desconectada</div>'
                    }
                </div>
                <div class="camera-controls">
                    <button class="btn btn-sm btn-info camera-details-btn" data-camera-id="${camera.id}">
                        <i class="fas fa-info-circle"></i>
                    </button>
                    <button class="btn btn-sm btn-primary camera-fullscreen-btn" data-camera-id="${camera.id}">
                        <i class="fas fa-expand"></i>
                    </button>
                    ${camera.ptz_capable 
                        ? `<button class="btn btn-sm btn-secondary camera-ptz-btn" data-camera-id="${camera.id}">
                            <i class="fas fa-arrows-alt"></i>
                           </button>`
                        : ''
                    }
                </div>
            `;
            
            grid.appendChild(cameraElement);
            
            // Agregar event listeners a los botones
            cameraElement.querySelector('.camera-details-btn').addEventListener('click', () => {
                this.showCameraDetails(camera.id);
            });
            
            cameraElement.querySelector('.camera-fullscreen-btn').addEventListener('click', () => {
                this.focusCamera(camera.id);
            });
            
            if (camera.ptz_capable) {
                cameraElement.querySelector('.camera-ptz-btn').addEventListener('click', () => {
                    this.openPTZControls(camera.id);
                });
            }
            
            // Iniciar streaming si la cámara está online
            if (camera.status === 'online') {
                this.startStreaming(camera.id);
            }
        });
        
        // Si está en vista '1x1' y hay una cámara seleccionada, mostrar controles adicionales
        if (this.layout === '1x1' && this.selectedCamera) {
            this.showEnhancedControls(this.selectedCamera);
        }
    }
    
    /**
     * Iniciar streaming para una cámara
     */
    startStreaming(cameraId) {
        const camera = this.cameras.get(cameraId);
        if (!camera || camera.status !== 'online') return;
        
        const streamContainer = document.getElementById(`stream-${cameraId}`);
        if (!streamContainer) return;
        
        // En un sistema real, aquí se conectaría al endpoint de streaming
        // Por ahora simularemos con un placeholder de imagen o video
        
        if (camera.stream_type === 'hls') {
            // Streaming HLS (HTTP Live Streaming)
            streamContainer.innerHTML = `
                <video id="video-${cameraId}" class="camera-video" controls autoplay muted></video>
            `;
            
            const videoElement = document.getElementById(`video-${cameraId}`);
            
            // En una implementación real, cargaríamos la librería HLS.js
            // y configuraríamos el streaming. Aquí es simulado.
            setTimeout(() => {
                videoElement.poster = camera.thumbnail_url || 'assets/camera-placeholder.jpg';
                
                // Simular carga de video
                if (camera.demo_video_url) {
                    videoElement.src = camera.demo_video_url;
                    videoElement.play().catch(e => console.log('Autoplay prevented:', e));
                }
            }, 500);
            
            // Almacenar referencia del stream activo
            this.activeStreams.set(cameraId, {
                type: 'hls',
                element: videoElement
            });
            
        } else if (camera.stream_type === 'mjpeg') {
            // Streaming MJPEG
            streamContainer.innerHTML = `
                <img id="mjpeg-${cameraId}" class="camera-feed" 
                    src="${camera.stream_url || camera.thumbnail_url || 'assets/camera-placeholder.jpg'}" 
                    alt="${camera.name}">
            `;
            
            // Almacenar referencia del stream activo
            this.activeStreams.set(cameraId, {
                type: 'mjpeg',
                element: document.getElementById(`mjpeg-${cameraId}`)
            });
            
        } else {
            // Tipo de streaming no soportado, mostrar imagen estática
            streamContainer.innerHTML = `
                <img class="camera-feed" 
                    src="${camera.thumbnail_url || 'assets/camera-placeholder.jpg'}" 
                    alt="${camera.name}">
                <div class="stream-overlay">Vista previa</div>
            `;
        }
    }
    
    /**
     * Detener streaming para una cámara
     */
    stopStreaming(cameraId) {
        if (!this.activeStreams.has(cameraId)) return;
        
        const stream = this.activeStreams.get(cameraId);
        
        if (stream.type === 'hls' && stream.element) {
            // Detener reproducción de video
            stream.element.pause();
            stream.element.src = '';
        }
        
        // Eliminar del registro de streams activos
        this.activeStreams.delete(cameraId);
    }
    
    /**
     * Detener todos los streams activos
     */
    stopAllStreams() {
        this.activeStreams.forEach((stream, cameraId) => {
            this.stopStreaming(cameraId);
        });
        
        this.activeStreams.clear();
    }
    
    /**
     * Mostrar detalles de una cámara
     */
    showCameraDetails(cameraId) {
        const camera = this.cameras.get(cameraId);
        if (!camera) return;
        
        const detailPanel = document.getElementById('camera-detail-panel');
        const detailsContent = document.getElementById('camera-details-content');
        
        if (!detailPanel || !detailsContent) return;
        
        // Actualizar título
        document.getElementById('camera-detail-title').textContent = camera.name;
        
        // Construir contenido de detalles
        detailsContent.innerHTML = `
            <div class="camera-metadata">
                <div class="row">
                    <div class="col-md-6">
                        <dl>
                            <dt>ID:</dt>
                            <dd>${camera.id}</dd>
                            
                            <dt>Ubicación:</dt>
                            <dd>${camera.location || 'No especificada'}</dd>
                            
                            <dt>Estado:</dt>
                            <dd>
                                <span class="badge badge-${camera.status === 'online' ? 'success' : 'danger'}">
                                    ${camera.status === 'online' ? 'En línea' : 'Fuera de línea'}
                                </span>
                            </dd>
                            
                            <dt>Tipo:</dt>
                            <dd>${camera.type || 'Standard'}</dd>
                        </dl>
                    </div>
                    <div class="col-md-6">
                        <dl>
                            <dt>Modelo:</dt>
                            <dd>${camera.model || 'Desconocido'}</dd>
                            
                            <dt>Resolución:</dt>
                            <dd>${camera.resolution || 'Estándar'}</dd>
                            
                            <dt>PTZ:</dt>
                            <dd>${camera.ptz_capable ? 'Sí' : 'No'}</dd>
                            
                            <dt>Última actualización:</dt>
                            <dd>${camera.last_update ? new Date(camera.last_update * 1000).toLocaleString() : 'N/A'}</dd>
                        </dl>
                    </div>
                </div>
            </div>
            
            <div class="camera-actions mt-3">
                <button class="btn btn-sm btn-primary camera-focus-btn" data-camera-id="${camera.id}">
                    <i class="fas fa-search-plus mr-1"></i> Enfocar
                </button>
                
                ${camera.ptz_capable ? `
                    <button class="btn btn-sm btn-secondary camera-ptz-panel-btn" data-camera-id="${camera.id}">
                        <i class="fas fa-arrows-alt mr-1"></i> Controles PTZ
                    </button>
                ` : ''}
                
                ${camera.recording_enabled ? `
                    <button class="btn btn-sm btn-info camera-recordings-btn" data-camera-id="${camera.id}">
                        <i class="fas fa-video mr-1"></i> Ver grabaciones
                    </button>
                ` : ''}
                
                <button class="btn btn-sm btn-warning camera-settings-btn" data-camera-id="${camera.id}">
                    <i class="fas fa-cog mr-1"></i> Configuración
                </button>
            </div>
            
            ${camera.map_location ? `
                <div class="camera-map mt-3">
                    <strong>Ubicación en mapa:</strong>
                    <div class="camera-map-container" id="camera-map-${camera.id}">
                        <!-- Aquí se cargaría un mapa en la implementación real -->
                        <div class="map-placeholder">Mapa de ubicación</div>
                    </div>
                </div>
            ` : ''}
        `;
        
        // Mostrar panel
        detailPanel.classList.remove('d-none');
        
        // Configurar event listeners para botones
        detailsContent.querySelector('.camera-focus-btn').addEventListener('click', () => {
            this.focusCamera(camera.id);
            this.hideCameraDetails();
        });
        
        if (camera.ptz_capable) {
            detailsContent.querySelector('.camera-ptz-panel-btn').addEventListener('click', () => {
                this.openPTZControls(camera.id);
            });
        }
        
        if (camera.recording_enabled) {
            detailsContent.querySelector('.camera-recordings-btn').addEventListener('click', () => {
                this.openRecordings(camera.id);
            });
        }
        
        detailsContent.querySelector('.camera-settings-btn').addEventListener('click', () => {
            this.openCameraSettings(camera.id);
        });
    }
    
    /**
     * Ocultar panel de detalles
     */
    hideCameraDetails() {
        const detailPanel = document.getElementById('camera-detail-panel');
        if (detailPanel) {
            detailPanel.classList.add('d-none');
        }
    }
    
    /**
     * Enfocar una cámara (modo 1x1)
     */
    focusCamera(cameraId) {
        this.selectedCamera = cameraId;
        this.changeLayout('1x1');
        
        // Notificar a listeners
        this.triggerCameraSelected(cameraId);
    }
    
    /**
     * Mostrar controles mejorados para una cámara en modo 1x1
     */
    showEnhancedControls(cameraId) {
        const camera = this.cameras.get(cameraId);
        if (!camera) return;
        
        const cameraCell = document.getElementById(`camera-cell-${cameraId}`);
        if (!cameraCell) return;
        
        // Añadir controles adicionales al contenedor principal
        const enhancedControls = document.createElement('div');
        enhancedControls.className = 'enhanced-controls mt-3';
        enhancedControls.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div class="camera-info">
                    <h4>${camera.name}</h4>
                    <p class="text-muted">${camera.location || 'Sin ubicación'}</p>
                </div>
                <div class="d-flex">
                    <button class="btn btn-outline-secondary back-to-grid-btn mr-2">
                        <i class="fas fa-th-large mr-1"></i> Volver a cuadrícula
                    </button>
                    <button class="btn btn-outline-primary camera-snapshot-btn">
                        <i class="fas fa-camera mr-1"></i> Capturar imagen
                    </button>
                </div>
            </div>
            
            ${camera.ptz_capable ? `
                <div class="camera-ptz-controls mt-3" id="ptz-controls-${cameraId}">
                    <div class="d-flex justify-content-between">
                        <div class="direction-controls">
                            <div class="btn-group-vertical">
                                <button class="btn btn-sm btn-secondary ptz-up-btn" data-direction="up">
                                    <i class="fas fa-arrow-up"></i>
                                </button>
                                <button class="btn btn-sm btn-secondary ptz-down-btn" data-direction="down">
                                    <i class="fas fa-arrow-down"></i>
                                </button>
                            </div>
                            <div class="btn-group mt-2">
                                <button class="btn btn-sm btn-secondary ptz-left-btn" data-direction="left">
                                    <i class="fas fa-arrow-left"></i>
                                </button>
                                <button class="btn btn-sm btn-secondary ptz-home-btn" data-direction="home">
                                    <i class="fas fa-home"></i>
                                </button>
                                <button class="btn btn-sm btn-secondary ptz-right-btn" data-direction="right">
                                    <i class="fas fa-arrow-right"></i>
                                </button>
                            </div>
                        </div>
                        <div class="zoom-controls">
                            <button class="btn btn-sm btn-secondary ptz-zoom-in-btn" data-zoom="in">
                                <i class="fas fa-search-plus"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary mt-2 ptz-zoom-out-btn" data-zoom="out">
                                <i class="fas fa-search-minus"></i>
                            </button>
                        </div>
                    </div>
                </div>
            ` : ''}
        `;
        
        cameraCell.appendChild(enhancedControls);
        
        // Configurar eventos para los controles
        enhancedControls.querySelector('.back-to-grid-btn').addEventListener('click', () => {
            this.selectedCamera = null;
            this.changeLayout('2x2'); // Volver a layout predeterminado
        });
        
        enhancedControls.querySelector('.camera-snapshot-btn').addEventListener('click', () => {
            this.takeSnapshot(cameraId);
        });
        
        // Configurar controles PTZ si están disponibles
        if (camera.ptz_capable) {
            const ptzControls = document.getElementById(`ptz-controls-${cameraId}`);
            
            ptzControls.querySelectorAll('.btn[data-direction]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const direction = btn.getAttribute('data-direction');
                    this.sendPTZCommand(cameraId, direction);
                });
            });
            
            ptzControls.querySelectorAll('.btn[data-zoom]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const zoom = btn.getAttribute('data-zoom');
                    this.sendPTZCommand(cameraId, zoom === 'in' ? 'zoom_in' : 'zoom_out');
                });
            });
        }
    }
    
    /**
     * Enviar comando PTZ a una cámara
     */
    sendPTZCommand(cameraId, command) {
        console.log(`Sending PTZ command: ${command} to camera ${cameraId}`);
        
        // En una implementación real, enviaríamos el comando a la API
        fetch(`${this.apiEndpoint}/${cameraId}/ptz`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command })
        })
        .then(response => response.json())
        .then(data => {
            console.log('PTZ command response:', data);
        })
        .catch(error => {
            console.error('Error sending PTZ command:', error);
        });
    }
    
    /**
     * Tomar una captura de pantalla de la cámara
     */
    takeSnapshot(cameraId) {
        console.log(`Taking snapshot from camera ${cameraId}`);
        
        // En una implementación real, solicitaríamos una captura a la API
        fetch(`${this.apiEndpoint}/${cameraId}/snapshot`, {
            method: 'POST'
        })
        .then(response => response.blob())
        .then(blob => {
            // Crear URL para la imagen
            const url = URL.createObjectURL(blob);
            
            // Abrir en nueva ventana o descargar
            const a = document.createElement('a');
            a.href = url;
            a.download = `snapshot_${cameraId}_${new Date().getTime()}.jpg`;
            a.click();
            
            // Liberar URL
            URL.revokeObjectURL(url);
        })
        .catch(error => {
            console.error('Error taking snapshot:', error);
        });
    }
    
    /**
     * Abrir panel de control PTZ
     */
    openPTZControls(cameraId) {
        // Si estamos en modo 1x1, los controles ya se muestran
        if (this.layout === '1x1' && this.selectedCamera === cameraId) {
            return;
        }
        
        // Enfocar la cámara y mostrar los controles
        this.focusCamera(cameraId);
    }
    
    /**
     * Abrir panel de grabaciones
     */
    openRecordings(cameraId) {
        console.log(`Opening recordings for camera ${cameraId}`);
        
        // Aquí implementaríamos la apertura de una modal o panel con grabaciones
        // En una aplicación real, esto sería un componente mucho más complejo
    }
    
    /**
     * Abrir configuración de cámara
     */
    openCameraSettings(cameraId) {
        console.log(`Opening settings for camera ${cameraId}`);
        
        // Aquí implementaríamos la apertura de un panel de configuración
    }
    
    /**
     * Registrar un callback para el evento de selección de cámara
     */
    onCameraSelected(callback) {
        if (typeof callback === 'function') {
            this.eventListeners.cameraSelected.push(callback);
        }
    }
    
    /**
     * Notificar a los suscriptores sobre la selección de una cámara
     */
    triggerCameraSelected(cameraId) {
        this.eventListeners.cameraSelected.forEach(callback => {
            try {
                callback(cameraId, this.cameras.get(cameraId));
            } catch (error) {
                console.error('Error in camera selected callback:', error);
            }
        });
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CameraViewPanel };
} 