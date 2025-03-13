/**
 * Panel de Alertas de Seguridad para el Dashboard
 * 
 * Gestiona la visualización y manejo de alertas de seguridad en tiempo real.
 */
class SecurityAlertsDashboard {
    /**
     * Inicializa el panel de alertas
     * @param {string} containerId ID del contenedor HTML
     * @param {string} apiEndpoint Endpoint de la API para alertas
     */
    constructor(containerId, apiEndpoint) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with ID ${containerId} not found`);
            return;
        }
        
        this.apiEndpoint = apiEndpoint;
        this.alertsQueue = [];
        this.activeAlerts = new Map();
        this.acknowledgedAlerts = new Map();
        this.eventListeners = {
            alertSelected: [],
            userAction: []
        };
        
        this.initialize();
    }
    
    /**
     * Inicializar componentes de la UI
     */
    initialize() {
        // Crear estructura básica si no existe
        if (!document.getElementById('alerts-container')) {
            this.container.innerHTML = `
                <div class="alerts-controls">
                    <div class="d-flex justify-content-between mb-3">
                        <div class="filters">
                            <select id="priority-filter" class="custom-select">
                                <option value="all">Todas las prioridades</option>
                                <option value="high">Alta prioridad</option>
                                <option value="medium">Media prioridad</option>
                                <option value="low">Baja prioridad</option>
                            </select>
                            <select id="type-filter" class="custom-select ml-2">
                                <option value="all">Todos los tipos</option>
                                <option value="intrusion">Intrusión</option>
                                <option value="theft_detected">Robo</option>
                                <option value="loitering">Merodeo</option>
                                <option value="perimeter_breach">Violación de Perímetro</option>
                                <option value="tailgating">Acceso no autorizado</option>
                            </select>
                        </div>
                        <div class="view-controls">
                            <button id="view-active" class="btn btn-primary active">Activas</button>
                            <button id="view-acknowledged" class="btn btn-secondary">Reconocidas</button>
                        </div>
                    </div>
                    <div class="search-box mb-3">
                        <input type="text" id="alert-search" class="form-control" 
                            placeholder="Buscar por ID, ubicación, tipo...">
                    </div>
                </div>
                <div id="alerts-container" class="alerts-list">
                    <div class="alert-placeholder text-center p-5 text-muted">
                        <i class="fas fa-bell fa-3x mb-3"></i>
                        <p>No hay alertas para mostrar</p>
                    </div>
                </div>
                <div id="alert-detail-panel" class="alert-detail d-none">
                    <div class="detail-header d-flex justify-content-between">
                        <h3 id="detail-title">Detalles de la Alerta</h3>
                        <button id="close-detail" class="btn btn-sm btn-light">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div id="alert-details-content"></div>
                </div>
            `;
            
            // Configurar event listeners
            this.setupEventListeners();
        }
        
        // Cargar alertas iniciales
        this.loadAlerts();
    }
    
    /**
     * Configurar event listeners para controles de la UI
     */
    setupEventListeners() {
        // Filtro por prioridad
        const priorityFilter = document.getElementById('priority-filter');
        if (priorityFilter) {
            priorityFilter.addEventListener('change', () => {
                this.applyFilters();
            });
        }
        
        // Filtro por tipo
        const typeFilter = document.getElementById('type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                this.applyFilters();
            });
        }
        
        // Búsqueda
        const searchBox = document.getElementById('alert-search');
        if (searchBox) {
            searchBox.addEventListener('input', () => {
                this.applyFilters();
            });
        }
        
        // Vista de alertas activas
        const viewActiveBtn = document.getElementById('view-active');
        if (viewActiveBtn) {
            viewActiveBtn.addEventListener('click', () => {
                viewActiveBtn.classList.add('active');
                document.getElementById('view-acknowledged').classList.remove('active');
                this.showActiveAlerts();
            });
        }
        
        // Vista de alertas reconocidas
        const viewAckBtn = document.getElementById('view-acknowledged');
        if (viewAckBtn) {
            viewAckBtn.addEventListener('click', () => {
                viewAckBtn.classList.add('active');
                document.getElementById('view-active').classList.remove('active');
                this.showAcknowledgedAlerts();
            });
        }
        
        // Cerrar panel de detalles
        const closeDetailBtn = document.getElementById('close-detail');
        if (closeDetailBtn) {
            closeDetailBtn.addEventListener('click', () => {
                this.hideAlertDetails();
            });
        }
        
        // Conectar con WebSocket
        this.connectWebSocket();
    }
    
    /**
     * Cargar alertas desde la API
     */
    loadAlerts() {
        fetch(this.apiEndpoint)
            .then(response => response.json())
            .then(data => {
                // Limpiar colecciones
                this.activeAlerts.clear();
                this.acknowledgedAlerts.clear();
                this.alertsQueue = [];
                
                // Clasificar alertas
                data.forEach(alert => {
                    if (alert.status === 'acknowledged') {
                        this.acknowledgedAlerts.set(alert.id, alert);
                    } else {
                        this.activeAlerts.set(alert.id, alert);
                        this.alertsQueue.push(alert.id);
                    }
                });
                
                // Renderizar alertas
                this.renderAlerts();
            })
            .catch(error => {
                console.error('Error loading alerts:', error);
                // Mostrar mensaje de error
                const alertsContainer = document.getElementById('alerts-container');
                if (alertsContainer) {
                    alertsContainer.innerHTML = `
                        <div class="alert alert-danger m-3">
                            Error al cargar alertas. Por favor, intente nuevamente.
                        </div>
                    `;
                }
            });
    }
    
    /**
     * Conectar con WebSocket para alertas en tiempo real
     */
    connectWebSocket() {
        const wsUrl = this.apiEndpoint.replace(/^http/, 'ws') + '/ws';
        const socket = new WebSocket(wsUrl);
        
        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'new_alert') {
                    this.addAlert(data.alert);
                } else if (data.type === 'update_alert') {
                    this.updateAlert(data.alert.id, data.alert);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        socket.onclose = () => {
            // Reconectar después de un tiempo
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }
    
    /**
     * Aplicar filtros a las alertas
     */
    applyFilters() {
        const priorityFilter = document.getElementById('priority-filter').value;
        const typeFilter = document.getElementById('type-filter').value;
        const searchTerm = document.getElementById('alert-search').value.toLowerCase();
        
        // Determinar qué colección estamos mostrando
        const isShowingActive = document.getElementById('view-active').classList.contains('active');
        const alerts = isShowingActive ? this.activeAlerts : this.acknowledgedAlerts;
        
        // Filtrar alertas
        const filteredAlerts = Array.from(alerts.values()).filter(alert => {
            // Filtro de prioridad
            if (priorityFilter !== 'all' && alert.priority !== priorityFilter) {
                return false;
            }
            
            // Filtro de tipo
            if (typeFilter !== 'all' && alert.type !== typeFilter) {
                return false;
            }
            
            // Filtro de búsqueda
            if (searchTerm) {
                const searchFields = [
                    alert.id.toString(),
                    alert.type,
                    alert.location,
                    alert.message,
                    alert.camera_id
                ].join(' ').toLowerCase();
                
                return searchFields.includes(searchTerm);
            }
            
            return true;
        });
        
        // Renderizar alertas filtradas
        this.renderAlerts(filteredAlerts);
    }
    
    /**
     * Mostrar alertas activas
     */
    showActiveAlerts() {
        this.renderAlerts();
    }
    
    /**
     * Mostrar alertas reconocidas
     */
    showAcknowledgedAlerts() {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;
        
        // Comprobar si hay alertas reconocidas
        if (this.acknowledgedAlerts.size === 0) {
            alertsContainer.innerHTML = `
                <div class="alert-placeholder text-center p-5 text-muted">
                    <i class="fas fa-check-circle fa-3x mb-3"></i>
                    <p>No hay alertas reconocidas</p>
                </div>
            `;
            return;
        }
        
        // Construir lista de alertas reconocidas
        alertsContainer.innerHTML = '';
        
        // Ordenar por timestamp
        const sortedAlerts = Array.from(this.acknowledgedAlerts.values())
            .sort((a, b) => b.timestamp - a.timestamp);
        
        // Renderizar cada alerta
        sortedAlerts.forEach(alert => {
            const alertElement = document.createElement('div');
            alertElement.id = `alert-${alert.id}`;
            alertElement.className = `alert-item alert-acknowledged alert-${alert.priority}`;
            this.renderAlertItem(alertElement, alert);
            alertsContainer.appendChild(alertElement);
        });
    }
    
    /**
     * Añadir nueva alerta
     */
    addAlert(alert) {
        // Comprobar si ya existe
        if (this.activeAlerts.has(alert.id)) {
            this.updateAlert(alert.id, alert);
            return;
        }
        
        // Añadir a la colección
        this.activeAlerts.set(alert.id, alert);
        
        // Añadir al principio de la cola de visualización
        this.alertsQueue.unshift(alert.id);
        
        // Renderizar alertas
        this.renderAlerts();
        
        // Destacar nueva alerta
        setTimeout(() => {
            const alertElement = document.getElementById(`alert-${alert.id}`);
            if (alertElement) {
                alertElement.classList.add('new-alert');
                
                // Quitar destaque después de un tiempo
                setTimeout(() => {
                    alertElement.classList.remove('new-alert');
                }, 5000);
            }
        }, 100);
    }
    
    /**
     * Actualizar alerta existente
     */
    updateAlert(alertId, alertData) {
        // Actualizar en la colección
        if (this.activeAlerts.has(alertId)) {
            this.activeAlerts.set(alertId, alertData);
            
            // Actualizar elemento en la UI si existe
            const alertElement = document.getElementById(`alert-${alertId}`);
            if (alertElement) {
                this.renderAlertItem(alertElement, alertData);
            }
            
            // Actualizar detalles si está seleccionada
            if (document.getElementById('alert-details-content').getAttribute('data-alert-id') === alertId) {
                this.showAlertDetails(alertId);
            }
        } else if (this.acknowledgedAlerts.has(alertId)) {
            this.acknowledgedAlerts.set(alertId, alertData);
        }
    }
    
    /**
     * Renderizar lista de alertas
     */
    renderAlerts(alertsList) {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;
        
        // Si se proporciona una lista de alertas, usarla
        const alerts = alertsList || Array.from(this.activeAlerts.values());
        
        // Comprobar si hay alertas
        if (alerts.length === 0) {
            alertsContainer.innerHTML = `
                <div class="alert-placeholder text-center p-5 text-muted">
                    <i class="fas fa-bell-slash fa-3x mb-3"></i>
                    <p>No hay alertas activas</p>
                </div>
            `;
            return;
        }
        
        // Limpiar contenedor
        alertsContainer.innerHTML = '';
        
        // Renderizar cada alerta
        alerts.forEach(alert => {
            const alertElement = document.createElement('div');
            alertElement.id = `alert-${alert.id}`;
            alertElement.className = `alert-item alert-${alert.priority}`;
            alertElement.addEventListener('click', () => this.showAlertDetails(alert.id));
            
            this.renderAlertItem(alertElement, alert);
            alertsContainer.appendChild(alertElement);
        });
    }
    
    /**
     * Renderizar elemento individual de alerta
     */
    renderAlertItem(element, alert) {
        // Formatear timestamp
        const date = new Date(alert.timestamp * 1000);
        const timeStr = date.toLocaleTimeString();
        
        // Íconos según tipo de alerta
        const iconMap = {
            'intrusion': 'fa-user-secret',
            'theft_detected': 'fa-hand-rock',
            'loitering': 'fa-hourglass-half',
            'perimeter_breach': 'fa-door-open',
            'tailgating': 'fa-users',
            'default': 'fa-exclamation-triangle'
        };
        
        const icon = iconMap[alert.type] || iconMap.default;
        
        // Construir HTML
        element.innerHTML = `
            <div class="alert-header">
                <div class="alert-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="alert-title">
                    <h4>${this.formatAlertType(alert.type)}</h4>
                    <span class="alert-time">${timeStr}</span>
                </div>
                <div class="alert-priority">
                    <span class="badge badge-${this.getPriorityClass(alert.priority)}">
                        ${this.formatPriority(alert.priority)}
                    </span>
                </div>
            </div>
            <div class="alert-content">
                <p>${alert.message}</p>
                <div class="alert-location">
                    <i class="fas fa-map-marker-alt"></i> ${alert.location}
                </div>
            </div>
        `;
    }
    
    /**
     * Mostrar detalles de una alerta
     */
    showAlertDetails(alertId) {
        const detailPanel = document.getElementById('alert-detail-panel');
        const detailContent = document.getElementById('alert-details-content');
        
        if (!detailPanel || !detailContent) return;
        
        // Buscar alerta en colecciones
        let alert = this.activeAlerts.get(alertId);
        if (!alert) {
            alert = this.acknowledgedAlerts.get(alertId);
            if (!alert) return;
        }
        
        // Actualizar título
        document.getElementById('detail-title').textContent = 
            `Alerta: ${this.formatAlertType(alert.type)}`;
        
        // Guardar ID de alerta actual
        detailContent.setAttribute('data-alert-id', alertId);
        
        // Formatear timestamp
        const date = new Date(alert.timestamp * 1000);
        const dateTimeStr = date.toLocaleString();
        
        // Construir HTML de detalles
        detailContent.innerHTML = `
            <div class="alert-detail-header alert-${alert.priority}">
                <div class="row">
                    <div class="col-md-8">
                        <h2>${this.formatAlertType(alert.type)}</h2>
                        <p class="lead">${alert.message}</p>
                    </div>
                    <div class="col-md-4 text-right">
                        <span class="badge badge-${this.getPriorityClass(alert.priority)} badge-lg">
                            ${this.formatPriority(alert.priority)}
                        </span>
                        <div class="alert-timestamp mt-2">
                            <i class="far fa-clock"></i> ${dateTimeStr}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="alert-detail-body mt-4">
                <div class="row">
                    <div class="col-md-6">
                        <h4>Ubicación</h4>
                        <p><i class="fas fa-map-marker-alt"></i> ${alert.location}</p>
                        ${alert.camera_id ? `<p><i class="fas fa-camera"></i> Cámara: ${alert.camera_id}</p>` : ''}
                    </div>
                    <div class="col-md-6">
                        <h4>Estado</h4>
                        <p><span class="badge badge-${this.getStatusClass(alert.status)}">
                            ${this.formatStatus(alert.status)}
                        </span></p>
                        ${alert.assigned_to ? `<p><i class="fas fa-user"></i> Asignado a: ${alert.assigned_to}</p>` : ''}
                    </div>
                </div>
                
                ${alert.image_url ? `
                <div class="alert-media mt-4">
                    <h4>Imagen</h4>
                    <img src="${alert.image_url}" class="img-fluid alert-image" alt="Imagen de alerta">
                </div>` : ''}
                
                ${alert.video_url ? `
                <div class="alert-media mt-4">
                    <h4>Video</h4>
                    <div class="video-container">
                        <video controls src="${alert.video_url}" class="alert-video"></video>
                    </div>
                </div>` : ''}
                
                <div class="alert-actions mt-4">
                    <h4>Acciones</h4>
                    <div class="btn-group" role="group">
                        <button class="btn btn-primary action-btn" data-action="acknowledge">
                            <i class="fas fa-check"></i> Reconocer
                        </button>
                        <button class="btn btn-warning action-btn" data-action="escalate">
                            <i class="fas fa-arrow-up"></i> Escalar
                        </button>
                        <button class="btn btn-danger action-btn" data-action="dispatch">
                            <i class="fas fa-running"></i> Enviar Personal
                        </button>
                    </div>
                </div>
                
                ${alert.notes ? `
                <div class="alert-notes mt-4">
                    <h4>Notas</h4>
                    <div class="alert-notes-content p-3 bg-light">
                        ${alert.notes}
                    </div>
                </div>` : ''}
            </div>
        `;
        
        // Configurar event listeners para botones de acción
        detailContent.querySelectorAll('.action-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = button.getAttribute('data-action');
                this.executeAction(action, alertId);
            });
        });
        
        // Mostrar panel
        detailPanel.classList.remove('d-none');
        
        // Disparar evento de selección
        this.triggerAlertSelected(alertId, alert);
    }
    
    /**
     * Ocultar panel de detalles
     */
    hideAlertDetails() {
        const detailPanel = document.getElementById('alert-detail-panel');
        if (detailPanel) {
            detailPanel.classList.add('d-none');
        }
    }
    
    /**
     * Ejecutar acción en una alerta
     */
    executeAction(action, alertId) {
        // Obtener datos de la alerta
        const alert = this.activeAlerts.get(alertId);
        if (!alert) return;
        
        console.log(`Executing action ${action} on alert ${alertId}`);
        
        // Enviar solicitud a la API
        fetch(`${this.apiEndpoint}/${alertId}/actions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: action,
                timestamp: Math.floor(Date.now() / 1000)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Actualizar UI según acción
                if (action === 'acknowledge') {
                    // Mover alerta a reconocidas
                    this.acknowledgeAlert(alertId);
                }
                
                // Disparar evento de acción de usuario
                this.triggerUserAction(action, {
                    alertId: alertId,
                    alertData: alert,
                    result: data
                });
            } else {
                console.error('Error executing action:', data.message);
            }
        })
        .catch(error => {
            console.error('Error executing action:', error);
        });
    }
    
    /**
     * Reconocer una alerta
     */
    acknowledgeAlert(alertId) {
        // Buscar la alerta
        const alert = this.activeAlerts.get(alertId);
        if (!alert) return;
        
        // Actualizar estado
        alert.status = 'acknowledged';
        
        // Mover a alertas reconocidas
        this.acknowledgedAlerts.set(alertId, alert);
        this.activeAlerts.delete(alertId);
        
        // Quitar de la cola
        this.alertsQueue = this.alertsQueue.filter(id => id !== alertId);
        
        // Si estamos mostrando alertas activas, actualizar vista
        if (document.getElementById('view-active').classList.contains('active')) {
            this.renderAlerts();
        }
        
        // Ocultar detalles si se está mostrando la alerta reconocida
        if (document.getElementById('alert-details-content').getAttribute('data-alert-id') === alertId) {
            this.hideAlertDetails();
        }
    }
    
    /**
     * Actualizar estado de una alerta
     */
    updateAlertStatus(alertId, status) {
        // Buscar la alerta en colecciones
        let alert = this.activeAlerts.get(alertId);
        let wasActive = true;
        
        if (!alert) {
            alert = this.acknowledgedAlerts.get(alertId);
            wasActive = false;
            if (!alert) return;
        }
        
        // Actualizar estado
        alert.status = status;
        
        // Mover entre colecciones si es necesario
        if (status === 'acknowledged' && wasActive) {
            this.acknowledgedAlerts.set(alertId, alert);
            this.activeAlerts.delete(alertId);
            this.alertsQueue = this.alertsQueue.filter(id => id !== alertId);
        } else if (status !== 'acknowledged' && !wasActive) {
            this.activeAlerts.set(alertId, alert);
            this.acknowledgedAlerts.delete(alertId);
            this.alertsQueue.unshift(alertId);
        }
        
        // Actualizar UI
        if ((wasActive && document.getElementById('view-active').classList.contains('active')) ||
            (!wasActive && document.getElementById('view-acknowledged').classList.contains('active'))) {
            this.renderAlerts();
        }
    }
    
    /**
     * Filtrar alertas por cámara
     */
    filterByCamera(cameraId) {
        // Buscar alertas de esta cámara
        const filteredAlerts = Array.from(this.activeAlerts.values())
            .filter(alert => alert.camera_id === cameraId);
        
        // Aplicar filtro
        this.renderAlerts(filteredAlerts);
        
        // Actualizar filtros visuales
        document.getElementById('alert-search').value = `Cámara ${cameraId}`;
    }
    
    /**
     * Registrar listener para selección de alertas
     */
    onAlertSelected(callback) {
        if (typeof callback === 'function') {
            this.eventListeners.alertSelected.push(callback);
        }
    }
    
    /**
     * Registrar listener para acciones de usuario
     */
    onUserAction(callback) {
        if (typeof callback === 'function') {
            this.eventListeners.userAction.push(callback);
        }
    }
    
    /**
     * Disparar evento de selección de alerta
     */
    triggerAlertSelected(alertId, alertData) {
        this.eventListeners.alertSelected.forEach(callback => {
            try {
                callback(alertId, alertData);
            } catch (error) {
                console.error('Error in alert selected callback:', error);
            }
        });
    }
    
    /**
     * Disparar evento de acción de usuario
     */
    triggerUserAction(action, data) {
        this.eventListeners.userAction.forEach(callback => {
            try {
                callback(action, data);
            } catch (error) {
                console.error('Error in user action callback:', error);
            }
        });
    }
    
    // Métodos auxiliares para formateo
    
    formatAlertType(type) {
        const typeMap = {
            'intrusion': 'Intrusión',
            'theft_detected': 'Robo Detectado',
            'loitering': 'Merodeo',
            'perimeter_breach': 'Violación de Perímetro',
            'tailgating': 'Acceso No Autorizado'
        };
        
        return typeMap[type] || type.replace('_', ' ');
    }
    
    formatPriority(priority) {
        const priorityMap = {
            'high': 'Alta',
            'medium': 'Media',
            'low': 'Baja'
        };
        
        return priorityMap[priority] || priority;
    }
    
    formatStatus(status) {
        const statusMap = {
            'new': 'Nueva',
            'acknowledged': 'Reconocida',
            'in_progress': 'En Proceso',
            'resolved': 'Resuelta',
            'false_alarm': 'Falsa Alarma'
        };
        
        return statusMap[status] || status;
    }
    
    getPriorityClass(priority) {
        const classMap = {
            'high': 'danger',
            'medium': 'warning',
            'low': 'info'
        };
        
        return classMap[priority] || 'secondary';
    }
    
    getStatusClass(status) {
        const classMap = {
            'new': 'danger',
            'acknowledged': 'primary',
            'in_progress': 'warning',
            'resolved': 'success',
            'false_alarm': 'secondary'
        };
        
        return classMap[status] || 'secondary';
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SecurityAlertsDashboard };
} 