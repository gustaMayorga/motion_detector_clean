/**
 * vigIA - Sistema de Vigilancia Inteligente con IA
 * Versión PMV (Proyecto MOTION_DETECTOR)
 *
 * © 2025 Gustavo Mayorga. Todos los derechos reservados.
 *
 * Este código es propiedad exclusiva de Gustavo Mayorga y está protegido por leyes de 
 * propiedad intelectual. Ninguna parte de este software puede ser reproducida, distribuida, 
 * o utilizada para crear trabajos derivados sin autorización explícita por escrito.
 *
 * Contacto legal: gustavo.mayorga.gm@gmail.com
 *
 * AVISO: El uso no autorizado de este código o sus conceptos está estrictamente prohibido
 * y será perseguido en la máxima medida permitida por la ley.
 */

/**
 * Panel de Control Unificado para el Sistema de Vigilancia con IA
 * 
 * Este componente integra las vistas de alertas, cámaras y estadísticas
 * en una interfaz cohesiva y reactiva para los operadores.
 */
class UnifiedControlPanel {
    /**
     * Inicializa el panel de control unificado
     * @param {Object} config Configuración del panel
     */
    constructor(config) {
        this.config = config;
        this.apiBaseUrl = config.apiBaseUrl || '/api';
        this.wsBaseUrl = config.wsBaseUrl || (window.location.protocol === 'https:' ? 
            'wss://' + window.location.host : 'ws://' + window.location.host);
            
        // Inicializar componentes
        this.alertsPanel = new SecurityAlertsDashboard(config.alertsContainerId, 
            `${this.apiBaseUrl}/alerts`);
        this.cameraPanel = new CameraViewPanel(config.cameraContainerId, 
            `${this.apiBaseUrl}/cameras`);
        this.statsPanel = new StatisticsPanel(config.statsContainerId, 
            `${this.apiBaseUrl}/stats`);
            
        // Estado de la aplicación
        this.state = {
            user: null,
            selectedAlert: null,
            activeTab: 'live',  // 'live', 'alerts', 'recordings'
            systemStatus: {
                cameras: { total: 0, online: 0, offline: 0 },
                alerts: { high: 0, medium: 0, low: 0, total: 0 },
                system: { cpu: 0, memory: 0, storage: 0 }
            }
        };
        
        // Websocket para actualizaciones en tiempo real
        this.socket = null;
        
        // Inicializar UI
        this.initialize();
    }
    
    /**
     * Inicializar interfaz de usuario y conexiones
     */
    initialize() {
        // Conectar eventos entre paneles
        this.connectPanelEvents();
        
        // Configurar navegación
        this.setupNavigation();
        
        // Iniciar conexión WebSocket
        this.connectWebSocket();
        
        // Cargar datos iniciales
        this.loadInitialData();
        
        // Configurar temporizadores de actualización
        this.setupTimers();
        
        // Escuchar eventos de teclado para atajos
        document.addEventListener('keydown', this.handleKeyboardShortcuts.bind(this));
    }
    
    /**
     * Conectar eventos entre paneles
     */
    connectPanelEvents() {
        // Cuando se selecciona una alerta, mostrar cámaras relevantes
        this.alertsPanel.onAlertSelected((alertId, alertData) => {
            this.state.selectedAlert = alertData;
            this.handleAlertSelected(alertId, alertData);
        });
        
        // Cuando se selecciona una cámara, mostrar alertas relevantes
        this.cameraPanel.onCameraSelected((cameraId) => {
            this.alertsPanel.filterByCamera(cameraId);
        });
        
        // Propagar eventos de usuario entre componentes
        this.alertsPanel.onUserAction((action, data) => {
            // Ejemplo: cuando un usuario reconoce una alerta
            if (action === 'acknowledge') {
                // Actualizar contador de alertas
                this.updateAlertCounter();
            }
        });
    }
    
    /**
     * Configurar navegación entre pestañas
     */
    setupNavigation() {
        const tabLinks = document.querySelectorAll('.tab-link');
        const tabContents = document.querySelectorAll('.tab-content');
        
        tabLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Obtener el target del enlace
                const tabId = link.getAttribute('data-tab');
                
                // Actualizar estado
                this.state.activeTab = tabId;
                
                // Actualizar clases activas
                tabLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
                
                // Mostrar contenido correspondiente
                tabContents.forEach(content => {
                    if (content.getAttribute('id') === tabId + '-tab') {
                        content.classList.add('active');
                    } else {
                        content.classList.remove('active');
                    }
                });
                
                // Eventos específicos según la pestaña
                if (tabId === 'live') {
                    this.cameraPanel.resumeStreams();
                } else {
                    this.cameraPanel.pauseStreams();
                }
            });
        });
    }
    
    /**
     * Establecer conexión WebSocket para actualizaciones en tiempo real
     */
    connectWebSocket() {
        try {
            this.socket = new WebSocket(`${this.wsBaseUrl}/ws/dashboard`);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.showNotification('Conexión en tiempo real establecida', 'success');
            };
            
            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showNotification('Error en la conexión en tiempo real', 'error');
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                
                // Intentar reconectar después de un tiempo
                setTimeout(() => {
                    if (this.socket?.readyState === WebSocket.CLOSED) {
                        this.connectWebSocket();
                    }
                }, 5000);
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
        }
    }
    
    /**
     * Manejar mensaje recibido por WebSocket
     */
    handleWebSocketMessage(data) {
        const { type, payload } = data;
        
        switch (type) {
            case 'new_alert':
                // Nueva alerta recibida
                this.alertsPanel.addAlert(payload);
                this.updateAlertCounter();
                this.playAlertSound(payload.priority);
                break;
                
            case 'camera_status':
                // Actualización de estado de cámara
                this.cameraPanel.updateCameraStatus(payload.camera_id, payload.status);
                this.updateCameraCounter();
                break;
                
            case 'system_stats':
                // Actualización de estadísticas del sistema
                this.statsPanel.updateStats(payload);
                this.updateSystemStatus(payload);
                break;
                
            case 'alert_update':
                // Actualización de una alerta existente
                this.alertsPanel.updateAlert(payload.id, payload);
                break;
                
            default:
                console.log('Unknown message type:', type, payload);
        }
    }
    
    /**
     * Cargar datos iniciales al abrir el dashboard
     */
    loadInitialData() {
        // Cargar alertas activas
        fetch(`${this.apiBaseUrl}/alerts/active`)
            .then(response => response.json())
            .then(data => {
                this.alertsPanel.setAlerts(data);
                this.updateAlertCounter();
            })
            .catch(error => {
                console.error('Error loading alerts:', error);
                this.showNotification('Error al cargar alertas', 'error');
            });
            
        // Cargar estado de cámaras
        fetch(`${this.apiBaseUrl}/cameras/status`)
            .then(response => response.json())
            .then(data => {
                this.cameraPanel.setCameras(data);
                this.updateCameraCounter();
            })
            .catch(error => {
                console.error('Error loading camera status:', error);
                this.showNotification('Error al cargar estado de cámaras', 'error');
            });
            
        // Cargar estadísticas del sistema
        fetch(`${this.apiBaseUrl}/stats/current`)
            .then(response => response.json())
            .then(data => {
                this.statsPanel.setStats(data);
                this.updateSystemStatus(data);
            })
            .catch(error => {
                console.error('Error loading system stats:', error);
            });
            
        // Cargar perfil de usuario
        if (this.config.userProfileUrl) {
            fetch(this.config.userProfileUrl)
                .then(response => response.json())
                .then(data => {
                    this.state.user = data;
                    this.updateUserProfile(data);
                })
                .catch(error => {
                    console.error('Error loading user profile:', error);
                });
        }
    }
    
    /**
     * Configurar temporizadores para actualización periódica
     */
    setupTimers() {
        // Actualizar estado de sistema cada minuto
        setInterval(() => {
            fetch(`${this.apiBaseUrl}/stats/current`)
                .then(response => response.json())
                .then(data => {
                    this.statsPanel.updateStats(data);
                    this.updateSystemStatus(data);
                })
                .catch(error => {
                    console.error('Error updating system stats:', error);
                });
        }, 60000);
        
        // Verificar estado de conexión cada 30 segundos
        setInterval(() => {
            if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
                this.connectWebSocket();
            }
        }, 30000);
    }
    
    /**
     * Manejar selección de alerta
     */
    handleAlertSelected(alertId, alertData) {
        // Mostrar cámaras relacionadas con la alerta
        if (alertData.camera_id) {
            this.cameraPanel.focusCamera(alertData.camera_id);
        }
        
        // Mostrar acciones contextuales para esta alerta
        this.displayContextualActions(alertData);
        
        // Si hay grabación, mostrar opción de reproducción
        if (alertData.video_url) {
            const videoPlayerContainer = document.getElementById('video-player-container');
            if (videoPlayerContainer) {
                videoPlayerContainer.classList.remove('hidden');
                this.loadVideoPlayer(alertData.video_url, alertData.type);
            }
        }
        
        // Actualizar mapa si la alerta tiene ubicación
        if (alertData.location && this.mapPanel) {
            this.mapPanel.centerOnLocation(alertData.location);
            this.mapPanel.addMarker(alertData.location, alertData.type);
        }
    }
    
    /**
     * Mostrar acciones contextuales para un tipo de alerta
     */
    displayContextualActions(alertData) {
        const actionsContainer = document.getElementById('contextual-actions');
        if (!actionsContainer) return;
        
        // Limpiar acciones anteriores
        actionsContainer.innerHTML = '';
        
        // Botones específicos según tipo de alerta
        let specificButtons = '';
        
        // Acciones específicas según el tipo de alerta
        switch (alertData.type) {
            case 'intrusion':
            case 'perimeter_breach':
                specificButtons += `
                    <button class="action-btn btn-danger" data-action="lockdown">
                        <i class="fas fa-lock"></i> Bloqueo
                    </button>
                    <button class="action-btn btn-warning" data-action="dispatch_security">
                        <i class="fas fa-running"></i> Enviar Seguridad
                    </button>
                `;
                break;
                
            case 'theft_detected':
                specificButtons += `
                    <button class="action-btn btn-warning" data-action="track_subject">
                        <i class="fas fa-crosshairs"></i> Seguir Sujeto
                    </button>
                    <button class="action-btn btn-info" data-action="save_evidence">
                        <i class="fas fa-save"></i> Guardar Evidencia
                    </button>
                `;
                break;
                
            case 'loitering':
                specificButtons += `
                    <button class="action-btn btn-info" data-action="make_announcement">
                        <i class="fas fa-bullhorn"></i> Anuncio
                    </button>
                `;
                break;
                
            case 'tailgating':
                specificButtons += `
                    <button class="action-btn btn-warning" data-action="verify_ids">
                        <i class="fas fa-id-card"></i> Verificar IDs
                    </button>
                `;
                break;
        }
        
        // Botones comunes para todas las alertas
        const commonButtons = `
            <button class="action-btn btn-primary" data-action="acknowledge">
                <i class="fas fa-check"></i> Reconocer
            </button>
            <button class="action-btn btn-danger" data-action="escalate">
                <i class="fas fa-exclamation-triangle"></i> Escalar
            </button>
            <button class="action-btn btn-secondary" data-action="review_video">
                <i class="fas fa-play-circle"></i> Ver Video
            </button>
        `;
        
        // Combinar botones
        actionsContainer.innerHTML = `
            <div class="d-flex justify-content-around flex-wrap">
                ${specificButtons}
                ${commonButtons}
            </div>
        `;
        
        // Agregar event listeners a los botones
        actionsContainer.querySelectorAll('.action-btn').forEach(button => {
            button.addEventListener('click', () => {
                const action = button.getAttribute('data-action');
                this.executeAction(action, alertData);
            });
        });
    }
    
    /**
     * Ejecutar acción seleccionada
     */
    executeAction(action, alertData) {
        console.log(`Executing action: ${action}`, alertData);
        
        // Enviar acción al servidor
        fetch(`${this.apiBaseUrl}/alerts/${alertData.id}/actions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: action,
                user: this.state.user ? this.state.user.id : null,
                timestamp: Date.now() / 1000
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Action response:', data);
            
            // Actualizar UI según la respuesta
            if (data.success) {
                // Mostrar notificación de éxito
                this.showNotification(`Acción "${action}" ejecutada correctamente`, 'success');
                
                // Acciones específicas según el tipo
                switch (action) {
                    case 'acknowledge':
                        this.alertsPanel.updateAlertStatus(alertData.id, 'acknowledged');
                        break;
                        
                    case 'escalate':
                        this.alertsPanel.updateAlertStatus(alertData.id, 'escalated');
                        break;
                        
                    case 'review_video':
                        if (alertData.video_url) {
                            this.openVideoModal(alertData.video_url, alertData.type);
                        }
                        break;
                }
            } else {
                // Mostrar error
                this.showNotification(`Error al ejecutar acción: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error executing action:', error);
            this.showNotification('Error de conexión al ejecutar la acción', 'error');
        });
    }
    
    /**
     * Mostrar notificación en la UI
     */
    showNotification(message, type = 'info') {
        const notificationArea = document.getElementById('notification-area');
        if (!notificationArea) return;
        
        const notificationId = 'notification-' + Date.now();
        const notificationHtml = `
            <div id="${notificationId}" class="notification notification-${type}">
                <span class="notification-message">${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;
        
        notificationArea.insertAdjacentHTML('beforeend', notificationHtml);
        
        // Agregar event listener para cerrar la notificación
        document.getElementById(notificationId).querySelector('.notification-close')
            .addEventListener('click', () => {
                const notification = document.getElementById(notificationId);
                notification.classList.add('notification-hiding');
                setTimeout(() => {
                    notification.remove();
                }, 300);
            });
            
        // Auto-ocultar después de un tiempo
        setTimeout(() => {
            const notification = document.getElementById(notificationId);
            if (notification) {
                notification.classList.add('notification-hiding');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);
    }
    
    /**
     * Reproducir sonido de alerta según prioridad
     */
    playAlertSound(priority) {
        // Verificar si hay soporte de audio
        if (!window.Audio) return;
        
        let soundFile;
        switch (priority) {
            case 'high':
                soundFile = this.config.sounds?.highPriority || 'assets/sounds/high_priority.mp3';
                break;
            case 'medium':
                soundFile = this.config.sounds?.mediumPriority || 'assets/sounds/medium_priority.mp3';
                break;
            default:
                soundFile = this.config.sounds?.lowPriority || 'assets/sounds/notification.mp3';
        }
        
        try {
            const audio = new Audio(soundFile);
            audio.play();
        } catch (e) {
            console.error('Error playing sound:', e);
        }
    }
    
    /**
     * Actualizar contador de alertas
     */
    updateAlertCounter() {
        fetch(`${this.apiBaseUrl}/alerts/count`)
            .then(response => response.json())
            .then(data => {
                this.state.systemStatus.alerts = data;
                
                // Actualizar badge de alertas
                const alertBadge = document.getElementById('alert-badge');
                if (alertBadge) {
                    alertBadge.textContent = data.total;
                    alertBadge.classList.toggle('hidden', data.total === 0);
                }
                
                // Actualizar contadores específicos
                const highPriorityCounter = document.getElementById('high-priority-counter');
                if (highPriorityCounter) {
                    highPriorityCounter.textContent = data.high;
                }
                
                const mediumPriorityCounter = document.getElementById('medium-priority-counter');
                if (mediumPriorityCounter) {
                    mediumPriorityCounter.textContent = data.medium;
                }
                
                const lowPriorityCounter = document.getElementById('low-priority-counter');
                if (lowPriorityCounter) {
                    lowPriorityCounter.textContent = data.low;
                }
            })
            .catch(error => {
                console.error('Error updating alert counter:', error);
            });
    }
    
    /**
     * Actualizar contador de cámaras
     */
    updateCameraCounter() {
        fetch(`${this.apiBaseUrl}/cameras/count`)
            .then(response => response.json())
            .then(data => {
                this.state.systemStatus.cameras = data;
                
                // Actualizar contadores
                const totalCamerasCounter = document.getElementById('total-cameras-counter');
                if (totalCamerasCounter) {
                    totalCamerasCounter.textContent = data.total;
                }
                
                const onlineCamerasCounter = document.getElementById('online-cameras-counter');
                if (onlineCamerasCounter) {
                    onlineCamerasCounter.textContent = data.online;
                }
                
                const offlineCamerasCounter = document.getElementById('offline-cameras-counter');
                if (offlineCamerasCounter) {
                    offlineCamerasCounter.textContent = data.offline;
                }
            })
            .catch(error => {
                console.error('Error updating camera counter:', error);
            });
    }
    
    /**
     * Actualizar estado del sistema
     */
    updateSystemStatus(data) {
        this.state.systemStatus.system = data;
        
        // Actualizar indicadores en la UI
        const cpuUsage = document.getElementById('cpu-usage');
        if (cpuUsage) {
            cpuUsage.textContent = `${data.cpu}%`;
            cpuUsage.style.width = `${data.cpu}%`;
            
            // Cambiar color según nivel
            if (data.cpu > 90) {
                cpuUsage.className = 'progress-bar bg-danger';
            } else if (data.cpu > 70) {
                cpuUsage.className = 'progress-bar bg-warning';
            } else {
                cpuUsage.className = 'progress-bar bg-success';
            }
        }
        
        const memoryUsage = document.getElementById('memory-usage');
        if (memoryUsage) {
            memoryUsage.textContent = `${data.memory}%`;
            memoryUsage.style.width = `${data.memory}%`;
            
            // Cambiar color según nivel
            if (data.memory > 90) {
                memoryUsage.className = 'progress-bar bg-danger';
            } else if (data.memory > 70) {
                memoryUsage.className = 'progress-bar bg-warning';
            } else {
                memoryUsage.className = 'progress-bar bg-success';
            }
        }
        
        const storageUsage = document.getElementById('storage-usage');
        if (storageUsage) {
            storageUsage.textContent = `${data.storage}%`;
            storageUsage.style.width = `${data.storage}%`;
            
            // Cambiar color según nivel
            if (data.storage > 90) {
                storageUsage.className = 'progress-bar bg-danger';
            } else if (data.storage > 70) {
                storageUsage.className = 'progress-bar bg-warning';
            } else {
                storageUsage.className = 'progress-bar bg-success';
            }
        }
    }
    
    /**
     * Actualizar perfil de usuario
     */
    updateUserProfile(userData) {
        const userNameElement = document.getElementById('user-name');
        if (userNameElement) {
            userNameElement.textContent = userData.name;
        }
        
        const userRoleElement = document.getElementById('user-role');
        if (userRoleElement) {
            userRoleElement.textContent = userData.role;
        }
        
        const userAvatarElement = document.getElementById('user-avatar');
        if (userAvatarElement && userData.avatar) {
            userAvatarElement.src = userData.avatar;
        }
    }
    
    /**
     * Abrir modal de video
     */
    openVideoModal(videoUrl, title) {
        const modalContainer = document.getElementById('video-modal-container');
        if (!modalContainer) return;
        
        // Crear modal si no existe
        if (!document.getElementById('video-modal')) {
            modalContainer.innerHTML = `
                <div id="video-modal" class="modal">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title"></h5>
                                <button type="button" class="close" data-dismiss="modal">&times;</button>
                            </div>
                            <div class="modal-body">
                                <video id="modal-video-player" controls class="w-100"></video>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Event listener para cerrar
            document.querySelector('#video-modal .close').addEventListener('click', () => {
                this.closeVideoModal();
            });
        }
        
        // Actualizar título y fuente de video
        document.querySelector('#video-modal .modal-title').textContent = 
            title ? `Video: ${title}` : 'Reproducción de video';
            
        const videoPlayer = document.getElementById('modal-video-player');
        videoPlayer.src = videoUrl;
        
        // Mostrar modal
        document.getElementById('video-modal').style.display = 'block';
        videoPlayer.play();
    }
    
    /**
     * Cerrar modal de video
     */
    closeVideoModal() {
        const modal = document.getElementById('video-modal');
        if (modal) {
            modal.style.display = 'none';
            
            // Detener reproducción
            const videoPlayer = document.getElementById('modal-video-player');
            if (videoPlayer) {
                videoPlayer.pause();
                videoPlayer.src = '';
            }
        }
    }
    
    /**
     * Manejar atajos de teclado
     */
    handleKeyboardShortcuts(event) {
        // ESC para cerrar modales
        if (event.key === 'Escape') {
            this.closeVideoModal();
        }
        
        // Ctrl+A para ir a panel de alertas
        if (event.ctrlKey && event.key === 'a') {
            event.preventDefault();
            document.querySelector('.tab-link[data-tab="alerts"]').click();
        }
        
        // Ctrl+C para ir a panel de cámaras
        if (event.ctrlKey && event.key === 'c') {
            event.preventDefault();
            document.querySelector('.tab-link[data-tab="live"]').click();
        }
        
        // Ctrl+S para ir a panel de estadísticas
        if (event.ctrlKey && event.key === 's') {
            event.preventDefault();
            document.querySelector('.tab-link[data-tab="stats"]').click();
        }
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UnifiedControlPanel };
} 