/**
 * Servicio de Alertas y Notificaciones
 * 
 * Gestiona la recepción y emisión de alertas del sistema de seguridad.
 */
class AlertService {
    /**
     * Inicializa el servicio de alertas
     * @param {string} apiEndpoint Endpoint base de la API
     * @param {string} wsEndpoint Endpoint para WebSocket
     */
    constructor(apiEndpoint = '/api', wsEndpoint) {
        this.apiEndpoint = apiEndpoint;
        this.wsEndpoint = wsEndpoint || (window.location.protocol === 'https:' ? 
            `wss://${window.location.host}/ws/alerts` : 
            `ws://${window.location.host}/ws/alerts`);
            
        this.socket = null;
        this.reconnectTimer = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // ms, aumentará con backoff
        
        this.alertListeners = new Map();
        this.alertCache = {
            active: new Map(),
            acknowledged: new Map(),
            all: []
        };
        
        // Conectar WebSocket
        this.connect();
    }
    
    /**
     * Conectar al WebSocket
     */
    connect() {
        try {
            // Limpiar temporizador existente
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            
            // Crear socket
            this.socket = new WebSocket(this.wsEndpoint);
            
            // Configurar manejo de eventos
            this.socket.onopen = this.handleSocketOpen.bind(this);
            this.socket.onmessage = this.handleSocketMessage.bind(this);
            this.socket.onclose = this.handleSocketClose.bind(this);
            this.socket.onerror = this.handleSocketError.bind(this);
        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    /**
     * Manejar apertura de conexión
     */
    handleSocketOpen() {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        // Solicitar alertas activas al conectar
        this.requestActiveAlerts();
    }
    
    /**
     * Manejar recepción de mensaje
     */
    handleSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            
            // Procesar según tipo de mensaje
            switch (data.type) {
                case 'new_alert':
                    this.processNewAlert(data.alert);
                    break;
                    
                case 'update_alert':
                    this.processAlertUpdate(data.alert);
                    break;
                    
                case 'active_alerts':
                    this.processActiveAlerts(data.alerts);
                    break;
                    
                default:
                    console.warn('Unknown message type:', data.type);
            }
        } catch (error) {
            console.error('Error processing WebSocket message:', error);
        }
    }
    
    /**
     * Manejar cierre de conexión
     */
    handleSocketClose(event) {
        if (event.wasClean) {
            console.log(`WebSocket closed cleanly, code=${event.code}, reason=${event.reason}`);
        } else {
            console.warn('WebSocket connection abruptly closed');
        }
        
        this.scheduleReconnect();
    }
    
    /**
     * Manejar error de conexión
     */
    handleSocketError(error) {
        console.error('WebSocket error:', error);
    }
    
    /**
     * Programar reconexión con backoff exponencial
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached, giving up');
            return;
        }
        
        // Calcular delay con backoff exponencial
        const delay = Math.min(30000, this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts));
        
        console.log(`Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }
    
    /**
     * Procesar nueva alerta
     */
    processNewAlert(alert) {
        // Guardar en caché
        this.alertCache.active.set(alert.id, alert);
        
        // Agregar al inicio del array de todas las alertas
        this.alertCache.all.unshift(alert);
        
        // Notificar a los suscriptores
        this.notifyAlertListeners('new', alert);
    }
    
    /**
     * Procesar actualización de alerta
     */
    processAlertUpdate(alert) {
        // Actualizar en caché según estado
        if (alert.status === 'acknowledged' || alert.status === 'resolved') {
            // Mover de activas a reconocidas
            this.alertCache.active.delete(alert.id);
            this.alertCache.acknowledged.set(alert.id, alert);
        } else {
            // Actualizar en la misma colección
            if (this.alertCache.active.has(alert.id)) {
                this.alertCache.active.set(alert.id, alert);
            } else if (this.alertCache.acknowledged.has(alert.id)) {
                this.alertCache.acknowledged.set(alert.id, alert);
            }
        }
        
        // Actualizar en array de todas
        const index = this.alertCache.all.findIndex(a => a.id === alert.id);
        if (index !== -1) {
            this.alertCache.all[index] = alert;
        }
        
        // Notificar a los suscriptores
        this.notifyAlertListeners('update', alert);
    }
    
    /**
     * Procesar lista de alertas activas
     */
    processActiveAlerts(alerts) {
        // Limpiar caché actual
        this.alertCache.active.clear();
        
        // Agregar alertas a la caché
        alerts.forEach(alert => {
            this.alertCache.active.set(alert.id, alert);
        });
        
        // Actualizar array completo
        this.loadAllAlerts();
        
        // Notificar a los suscriptores
        this.notifyAlertListeners('load', Array.from(this.alertCache.active.values()));
    }
    
    /**
     * Solicitar alertas activas al servidor
     */
    requestActiveAlerts() {
        // Si el socket está abierto, enviar solicitud
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'get_active_alerts'
            }));
        } else {
            // Intentar con HTTP
            this.loadActiveAlerts();
        }
    }
    
    /**
     * Cargar alertas activas mediante HTTP
     */
    async loadActiveAlerts() {
        try {
            const response = await fetch(`${this.apiEndpoint}/alerts/active`);
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const alerts = await response.json();
            this.processActiveAlerts(alerts);
            
            return alerts;
        } catch (error) {
            console.error('Error loading active alerts:', error);
            return [];
        }
    }
    
    /**
     * Cargar todas las alertas (historial)
     */
    async loadAllAlerts(page = 1, limit = 100) {
        try {
            const response = await fetch(`${this.apiEndpoint}/alerts?page=${page}&limit=${limit}`);
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Actualizar caché
            this.alertCache.all = data.alerts;
            
            // Notificar a los suscriptores
            this.notifyAlertListeners('history', data.alerts);
            
            return data;
        } catch (error) {
            console.error('Error loading alert history:', error);
            return { alerts: [], total: 0 };
        }
    }
    
    /**
     * Obtener una alerta por ID
     */
    async getAlert(alertId) {
        // Buscar en caché primero
        if (this.alertCache.active.has(alertId)) {
            return this.alertCache.active.get(alertId);
        }
        
        if (this.alertCache.acknowledged.has(alertId)) {
            return this.alertCache.acknowledged.get(alertId);
        }
        
        // Si no está en caché, cargar desde API
        try {
            const response = await fetch(`${this.apiEndpoint}/alerts/${alertId}`);
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const alert = await response.json();
            
            // Actualizar caché
            if (alert.status === 'new' || alert.status === 'in_progress') {
                this.alertCache.active.set(alertId, alert);
            } else {
                this.alertCache.acknowledged.set(alertId, alert);
            }
            
            return alert;
        } catch (error) {
            console.error(`Error loading alert ${alertId}:`, error);
            throw error;
        }
    }
    
    /**
     * Realizar acción sobre una alerta
     */
    async takeAction(alertId, action, data = {}) {
        try {
            const response = await fetch(`${this.apiEndpoint}/alerts/${alertId}/actions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action,
                    ...data
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `Error al ejecutar acción ${action}`);
            }
            
            // Actualizar caché si la respuesta incluye la alerta actualizada
            const result = await response.json();
            
            if (result.alert) {
                this.processAlertUpdate(result.alert);
            }
            
            return result;
        } catch (error) {
            console.error(`Error executing action ${action} on alert ${alertId}:`, error);
            throw error;
        }
    }
    
    /**
     * Reconocer una alerta
     */
    acknowledgeAlert(alertId, notes = '') {
        return this.takeAction(alertId, 'acknowledge', { notes });
    }
    
    /**
     * Marcar alerta como resuelta
     */
    resolveAlert(alertId, resolution = '', notes = '') {
        return this.takeAction(alertId, 'resolve', { resolution, notes });
    }
    
    /**
     * Marcar alerta como falsa alarma
     */
    markAsFalseAlarm(alertId, reason = '') {
        return this.takeAction(alertId, 'false_alarm', { reason });
    }
    
    /**
     * Escalar alerta a superior o autoridades
     */
    escalateAlert(alertId, recipient = '', notes = '') {
        return this.takeAction(alertId, 'escalate', { recipient, notes });
    }
    
    /**
     * Suscribirse a eventos de alertas
     * @param {string} event Tipo de evento ('new', 'update', 'load', 'history', '*')
     * @param {Function} callback Función a llamar cuando ocurra el evento
     * @returns {Function} Función para cancelar la suscripción
     */
    subscribe(event, callback) {
        if (!this.alertListeners.has(event)) {
            this.alertListeners.set(event, new Set());
        }
        
        const listeners = this.alertListeners.get(event);
        listeners.add(callback);
        
        // Retornar función para cancelar suscripción
        return () => {
            const listeners = this.alertListeners.get(event);
            if (listeners) {
                listeners.delete(callback);
            }
        };
    }
    
    /**
     * Notificar a los suscriptores sobre eventos de alertas
     * @param {string} event Tipo de evento
     * @param {Object|Array} data Datos del evento
     */
    notifyAlertListeners(event, data) {
        // Notificar a suscriptores del evento específico
        const specificListeners = this.alertListeners.get(event);
        if (specificListeners) {
            specificListeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in ${event} alert listener:`, error);
                }
            });
        }
        
        // Notificar a suscriptores de todos los eventos
        const allListeners = this.alertListeners.get('*');
        if (allListeners) {
            allListeners.forEach(callback => {
                try {
                    callback(event, data);
                } catch (error) {
                    console.error(`Error in global alert listener:`, error);
                }
            });
        }
    }
    
    /**
     * Cerrar conexión al destruir el servicio
     */
    destroy() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        this.alertListeners.clear();
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AlertService };
} 