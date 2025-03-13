/**
 * Servicio de Autenticación
 * 
 * Gestiona la autenticación, autorización y permisos de usuarios.
 */
class AuthService {
    /**
     * Inicializa el servicio de autenticación
     * @param {string} apiEndpoint Endpoint base de la API
     */
    constructor(apiEndpoint = '/api') {
        this.apiEndpoint = apiEndpoint;
        this.user = null;
        this.token = localStorage.getItem('auth_token');
        this.authListeners = [];
        this.refreshTimer = null;
        
        // Verificar si hay un token almacenado y validarlo
        if (this.token) {
            this.validateToken();
        }
    }
    
    /**
     * Iniciar sesión con credenciales
     * @param {string} username Nombre de usuario
     * @param {string} password Contraseña
     * @returns {Promise<Object>} Información del usuario autenticado
     */
    async login(username, password) {
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Error de autenticación');
            }
            
            const data = await response.json();
            
            // Guardar token y datos del usuario
            this.token = data.token;
            this.user = data.user;
            
            // Guardar en localStorage
            localStorage.setItem('auth_token', this.token);
            
            // Configurar temporizador para refrescar token
            this.setupTokenRefresh(data.expiresIn || 3600);
            
            // Notificar a los suscriptores
            this.notifyAuthChange(true);
            
            return this.user;
        } catch (error) {
            console.error('Error de inicio de sesión:', error);
            throw error;
        }
    }
    
    /**
     * Cerrar sesión del usuario actual
     * @returns {Promise<boolean>} Resultado de la operación
     */
    async logout() {
        try {
            // Intentar cerrar sesión en el servidor
            if (this.token) {
                await fetch(`${this.apiEndpoint}/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.token}`
                    }
                }).catch(err => console.warn('Error en logout:', err));
            }
            
            // Limpiar datos almacenados independientemente de la respuesta
            this.token = null;
            this.user = null;
            localStorage.removeItem('auth_token');
            
            // Detener temporizador de refresco
            if (this.refreshTimer) {
                clearTimeout(this.refreshTimer);
                this.refreshTimer = null;
            }
            
            // Notificar a los suscriptores
            this.notifyAuthChange(false);
            
            return true;
        } catch (error) {
            console.error('Error al cerrar sesión:', error);
            return false;
        }
    }
    
    /**
     * Verificar si el usuario está autenticado
     * @returns {boolean} Estado de autenticación
     */
    isAuthenticated() {
        return !!this.token && !!this.user;
    }
    
    /**
     * Obtener usuario actual
     * @returns {Object|null} Datos del usuario autenticado
     */
    getCurrentUser() {
        return this.user;
    }
    
    /**
     * Verificar si el usuario tiene un permiso específico
     * @param {string} permission Permiso a verificar
     * @returns {boolean} Si el usuario tiene el permiso
     */
    hasPermission(permission) {
        if (!this.user || !this.user.permissions) {
            return false;
        }
        
        return this.user.permissions.includes(permission);
    }
    
    /**
     * Verificar si el usuario pertenece a un rol
     * @param {string} role Rol a verificar
     * @returns {boolean} Si el usuario tiene el rol
     */
    hasRole(role) {
        if (!this.user || !this.user.roles) {
            return false;
        }
        
        return this.user.roles.includes(role);
    }
    
    /**
     * Validar token actual con el servidor
     * @returns {Promise<boolean>} Si el token es válido
     */
    async validateToken() {
        if (!this.token) {
            return false;
        }
        
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/validate`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (!response.ok) {
                // Token inválido, limpiar datos
                this.token = null;
                this.user = null;
                localStorage.removeItem('auth_token');
                this.notifyAuthChange(false);
                return false;
            }
            
            // Token válido, obtener datos del usuario
            const data = await response.json();
            this.user = data.user;
            
            // Actualizar token si se proporciona uno nuevo
            if (data.token) {
                this.token = data.token;
                localStorage.setItem('auth_token', this.token);
                this.setupTokenRefresh(data.expiresIn || 3600);
            }
            
            this.notifyAuthChange(true);
            return true;
        } catch (error) {
            console.error('Error validando token:', error);
            return false;
        }
    }
    
    /**
     * Refrescar token antes de que expire
     * @returns {Promise<boolean>} Si el refresco fue exitoso
     */
    async refreshToken() {
        if (!this.token) {
            return false;
        }
        
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (!response.ok) {
                // No se pudo refrescar el token
                return false;
            }
            
            const data = await response.json();
            
            // Actualizar token
            this.token = data.token;
            localStorage.setItem('auth_token', this.token);
            
            // Configurar próximo refresco
            this.setupTokenRefresh(data.expiresIn || 3600);
            
            return true;
        } catch (error) {
            console.error('Error refrescando token:', error);
            return false;
        }
    }
    
    /**
     * Configurar temporizador para refrescar token
     * @param {number} expiresIn Tiempo en segundos hasta expiración
     */
    setupTokenRefresh(expiresIn) {
        // Limpiar temporizador anterior si existe
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
        }
        
        // Configurar refresco para 5 minutos antes de expirar
        const refreshTime = Math.max((expiresIn - 300) * 1000, 0);
        
        this.refreshTimer = setTimeout(() => {
            this.refreshToken();
        }, refreshTime);
    }
    
    /**
     * Suscribirse a cambios en el estado de autenticación
     * @param {Function} callback Función a llamar cuando cambie el estado
     * @returns {Function} Función para cancelar la suscripción
     */
    onAuthChange(callback) {
        if (typeof callback === 'function') {
            this.authListeners.push(callback);
            
            // Notificar estado actual inmediatamente
            setTimeout(() => {
                callback(this.isAuthenticated(), this.user);
            }, 0);
            
            // Retornar función para cancelar suscripción
            return () => {
                const index = this.authListeners.indexOf(callback);
                if (index !== -1) {
                    this.authListeners.splice(index, 1);
                }
            };
        }
    }
    
    /**
     * Notificar a los suscriptores sobre cambios en la autenticación
     * @param {boolean} isAuthenticated Estado de autenticación
     */
    notifyAuthChange(isAuthenticated) {
        this.authListeners.forEach(callback => {
            try {
                callback(isAuthenticated, this.user);
            } catch (error) {
                console.error('Error en callback de autenticación:', error);
            }
        });
    }
    
    /**
     * Recuperar contraseña
     * @param {string} email Correo electrónico del usuario
     * @returns {Promise<boolean>} Resultado de la operación
     */
    async requestPasswordReset(email) {
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/reset-password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email })
            });
            
            return response.ok;
        } catch (error) {
            console.error('Error al solicitar recuperación de contraseña:', error);
            return false;
        }
    }
    
    /**
     * Cambiar contraseña con token de recuperación
     * @param {string} token Token de recuperación
     * @param {string} newPassword Nueva contraseña
     * @returns {Promise<boolean>} Resultado de la operación
     */
    async resetPassword(token, newPassword) {
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/reset-password/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token, newPassword })
            });
            
            return response.ok;
        } catch (error) {
            console.error('Error al cambiar contraseña:', error);
            return false;
        }
    }
    
    /**
     * Crear una nueva cuenta de usuario
     * @param {Object} userData Datos del nuevo usuario
     * @returns {Promise<Object>} Información del usuario creado
     */
    async register(userData) {
        try {
            const response = await fetch(`${this.apiEndpoint}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(userData)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Error al registrar usuario');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error al registrar usuario:', error);
            throw error;
        }
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AuthService };
} 