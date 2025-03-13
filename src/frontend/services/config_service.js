/**
 * Servicio de Configuración
 * 
 * Gestiona la carga, validación y actualización de configuraciones del sistema.
 */
class ConfigService {
    /**
     * Inicializa el servicio de configuración
     * @param {string} apiEndpoint Endpoint base de la API
     */
    constructor(apiEndpoint = '/api') {
        this.apiEndpoint = apiEndpoint;
        this.configCache = new Map();
        this.configListeners = new Map();
    }
    
    /**
     * Obtener configuración por nombre
     * @param {string} configName Nombre de la configuración
     * @param {boolean} forceRefresh Forzar recarga desde el servidor
     * @returns {Promise<Object>} Configuración solicitada
     */
    async getConfig(configName, forceRefresh = false) {
        // Si ya tenemos la configuración en caché y no se fuerza recarga
        if (!forceRefresh && this.configCache.has(configName)) {
            return this.configCache.get(configName);
        }
        
        // Cargar desde la API
        try {
            const response = await fetch(`${this.apiEndpoint}/config/${configName}`);
            
            if (!response.ok) {
                throw new Error(`Error loading config ${configName}: ${response.statusText}`);
            }
            
            const config = await response.json();
            
            // Guardar en caché
            this.configCache.set(configName, config);
            
            // Notificar a los suscriptores
            this.notifyConfigChange(configName, config);
            
            return config;
        } catch (error) {
            console.error('Config service error:', error);
            throw error;
        }
    }
    
    /**
     * Actualizar configuración
     * @param {string} configName Nombre de la configuración
     * @param {Object} configData Nuevos datos de configuración
     * @returns {Promise<Object>} Configuración actualizada
     */
    async updateConfig(configName, configData) {
        try {
            const response = await fetch(`${this.apiEndpoint}/config/${configName}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(configData)
            });
            
            if (!response.ok) {
                throw new Error(`Error updating config ${configName}: ${response.statusText}`);
            }
            
            const updatedConfig = await response.json();
            
            // Actualizar caché
            this.configCache.set(configName, updatedConfig);
            
            // Notificar a los suscriptores
            this.notifyConfigChange(configName, updatedConfig);
            
            return updatedConfig;
        } catch (error) {
            console.error('Config update error:', error);
            throw error;
        }
    }
    
    /**
     * Suscribirse a cambios en una configuración
     * @param {string} configName Nombre de la configuración
     * @param {Function} callback Función a llamar cuando la configuración cambie
     * @returns {Function} Función para cancelar la suscripción
     */
    subscribeToConfig(configName, callback) {
        if (!this.configListeners.has(configName)) {
            this.configListeners.set(configName, new Set());
        }
        
        const listeners = this.configListeners.get(configName);
        listeners.add(callback);
        
        // Si ya tenemos la configuración en caché, notificar inmediatamente
        if (this.configCache.has(configName)) {
            try {
                callback(this.configCache.get(configName));
            } catch (error) {
                console.error('Error in config subscriber callback:', error);
            }
        }
        
        // Retornar función para cancelar suscripción
        return () => {
            const listeners = this.configListeners.get(configName);
            if (listeners) {
                listeners.delete(callback);
            }
        };
    }
    
    /**
     * Notificar a los suscriptores sobre un cambio en la configuración
     * @param {string} configName Nombre de la configuración
     * @param {Object} configData Datos de configuración actualizados
     */
    notifyConfigChange(configName, configData) {
        const listeners = this.configListeners.get(configName);
        if (!listeners) return;
        
        listeners.forEach(callback => {
            try {
                callback(configData);
            } catch (error) {
                console.error('Error in config change callback:', error);
            }
        });
    }
    
    /**
     * Obtener información sobre todas las configuraciones disponibles
     * @returns {Promise<Array>} Lista de configuraciones disponibles
     */
    async listAvailableConfigs() {
        try {
            const response = await fetch(`${this.apiEndpoint}/config`);
            
            if (!response.ok) {
                throw new Error(`Error listing configs: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error listing configs:', error);
            throw error;
        }
    }
    
    /**
     * Validar configuración
     * @param {string} configName Nombre de la configuración
     * @param {Object} configData Datos de configuración a validar
     * @returns {Promise<Object>} Resultado de la validación
     */
    async validateConfig(configName, configData) {
        try {
            const response = await fetch(`${this.apiEndpoint}/config/${configName}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(configData)
            });
            
            const result = await response.json();
            
            return {
                valid: response.ok,
                errors: result.errors || [],
                warnings: result.warnings || []
            };
        } catch (error) {
            console.error('Config validation error:', error);
            return {
                valid: false,
                errors: [error.message],
                warnings: []
            };
        }
    }
    
    /**
     * Restablecer configuración a valores predeterminados
     * @param {string} configName Nombre de la configuración
     * @returns {Promise<Object>} Configuración restablecida
     */
    async resetConfig(configName) {
        try {
            const response = await fetch(`${this.apiEndpoint}/config/${configName}/reset`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`Error resetting config ${configName}: ${response.statusText}`);
            }
            
            const resetConfig = await response.json();
            
            // Actualizar caché
            this.configCache.set(configName, resetConfig);
            
            // Notificar a los suscriptores
            this.notifyConfigChange(configName, resetConfig);
            
            return resetConfig;
        } catch (error) {
            console.error('Config reset error:', error);
            throw error;
        }
    }
    
    /**
     * Limpiar caché de configuraciones
     */
    clearCache() {
        this.configCache.clear();
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ConfigService };
} 