<template>
  <div class="config-editor">
    <h1>Configuración del Sistema</h1>
    
    <div v-if="loading" class="loading-spinner">
      <div class="spinner"></div>
      <p>Cargando configuración...</p>
    </div>
    
    <div v-else-if="error" class="error-message">
      <i class="fas fa-exclamation-triangle"></i>
      <p>{{ error }}</p>
      <button @click="loadConfig" class="btn btn-primary">Reintentar</button>
    </div>
    
    <div v-else class="config-container">
      <!-- Pestañas de configuración -->
      <ul class="nav nav-tabs" role="tablist">
        <li class="nav-item" v-for="(section, index) in configSections" :key="index">
          <a class="nav-link" :class="{ active: activeSection === section.key }" 
             @click="activeSection = section.key" href="#" role="tab">
            {{ section.label }}
          </a>
        </li>
      </ul>
      
      <!-- Contenido de configuración por sección -->
      <div class="tab-content p-3 border border-top-0 rounded-bottom">
        <!-- Sección del sistema -->
        <div class="tab-pane fade" :class="{ 'show active': activeSection === 'system' }">
          <h3>Configuración General</h3>
          <form>
            <div class="form-group row">
              <label class="col-sm-3 col-form-label">Nombre del Sistema</label>
              <div class="col-sm-9">
                <input type="text" class="form-control" v-model="config.system.name">
              </div>
            </div>
            
            <div class="form-group row">
              <label class="col-sm-3 col-form-label">Versión</label>
              <div class="col-sm-9">
                <input type="text" class="form-control" v-model="config.system.version" readonly>
              </div>
            </div>
            
            <div class="form-group row">
              <label class="col-sm-3 col-form-label">Nivel de Log</label>
              <div class="col-sm-9">
                <select class="form-control" v-model="config.system.log_level">
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
            </div>
            
            <div class="form-group row">
              <label class="col-sm-3 col-form-label">Zona Horaria</label>
              <div class="col-sm-9">
                <input type="text" class="form-control" v-model="config.system.timezone">
              </div>
            </div>
            
            <div class="form-group row">
              <div class="col-sm-3">Modo Debug</div>
              <div class="col-sm-9">
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" v-model="config.system.enable_debug">
                </div>
              </div>
            </div>
          </form>
        </div>
        
        <!-- Sección de cámaras -->
        <div class="tab-pane fade" :class="{ 'show active': activeSection === 'cameras' }">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h3>Cámaras</h3>
            <button class="btn btn-primary" @click="addCamera">
              <i class="fas fa-plus"></i> Añadir Cámara
            </button>
          </div>
          
          <div v-if="config.cameras.length === 0" class="alert alert-info">
            No hay cámaras configuradas. Añade una nueva cámara haciendo clic en el botón "Añadir Cámara".
          </div>
          
          <div v-else class="camera-list">
            <div v-for="(camera, index) in config.cameras" :key="camera.id" class="card mb-3">
              <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">
                  <i class="fas fa-video"></i> {{ camera.name }}
                  <span v-if="!camera.enabled" class="badge badge-secondary ml-2">Desactivada</span>
                </h5>
                <div>
                  <button class="btn btn-sm btn-outline-primary mr-2" @click="editCamera(index)">
                    <i class="fas fa-edit"></i> Editar
                  </button>
                  <button class="btn btn-sm btn-outline-danger" @click="removeCamera(index)">
                    <i class="fas fa-trash"></i> Eliminar
                  </button>
                </div>
              </div>
              <div class="card-body">
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">URL</label>
                  <div class="col-sm-9">
                    <input type="text" class="form-control" v-model="camera.url">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Usuario</label>
                  <div class="col-sm-9">
                    <input type="text" class="form-control" v-model="camera.username">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Contraseña</label>
                  <div class="col-sm-9">
                    <input type="password" class="form-control" v-model="camera.password">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Resolución</label>
                  <div class="col-sm-9">
                    <input type="text" class="form-control" v-model="camera.resolution">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">FPS</label>
                  <div class="col-sm-9">
                    <input type="number" class="form-control" v-model.number="camera.fps" min="1" max="60" step="1">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Modo de Grabación</label>
                  <div class="col-sm-9">
                    <select class="form-control" v-model="camera.recording.mode">
                      <option value="motion">Movimiento</option>
                      <option value="all">Toda la Cámara</option>
                    </select>
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Pre-Grabación</label>
                  <div class="col-sm-9">
                    <input type="number" class="form-control" v-model.number="camera.recording.pre_record" min="0" max="10" step="1">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Post-Grabación</label>
                  <div class="col-sm-9">
                    <input type="number" class="form-control" v-model.number="camera.recording.post_record" min="0" max="10" step="1">
                  </div>
                </div>
                <div class="form-group row">
                  <label class="col-sm-3 col-form-label">Peso del módulo</label>
                  <div class="col-sm-9">
                    <input type="number" class="form-control" v-model.number="camera.weight" min="0.1" max="1.0" step="0.1">
                    <small class="form-text text-muted">Entre 0.1 y 1.0, donde 1.0 es el peso máximo</small>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" @click="closeCameraModal">Cancelar</button>
                <button type="button" class="btn btn-primary" @click="saveCamera">Guardar</button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="mt-4 d-flex justify-content-end">
        <button class="btn btn-secondary mr-2" @click="resetConfig">
          <i class="fas fa-undo"></i> Restablecer
        </button>
        <button class="btn btn-primary" @click="saveConfig" :disabled="saving">
          <i class="fas fa-save"></i> {{ saving ? 'Guardando...' : 'Guardar Configuración' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'ConfigEditor',
  data() {
    return {
      config: null,
      originalConfig: null,
      loading: true,
      saving: false,
      error: null,
      activeSection: 'system',
      configSections: [
        { key: 'system', label: 'Sistema' },
        { key: 'cameras', label: 'Cámaras' },
        { key: 'detection', label: 'Detección' },
        { key: 'storage', label: 'Almacenamiento' },
        { key: 'notifications', label: 'Notificaciones' },
        { key: 'agents', label: 'Agentes' }
      ],
      showCameraModal: false,
      showZoneModal: false,
      showAgentModal: false,
      editing: null,
      editingIndex: -1,
      editingParentIndex: -1,
      cameraVendors: [
        { value: 'hikvision', label: 'Hikvision' },
        { value: 'dahua', label: 'Dahua' },
        { value: 'axis', label: 'Axis' },
        { value: 'generic', label: 'RTSP Genérico' }
      ]
    };
  },
  created() {
    this.loadConfig();
  },
  methods: {
    async loadConfig() {
      this.loading = true;
      this.error = null;
      
      try {
        const response = await axios.get('/api/config');
        this.config = response.data;
        this.originalConfig = JSON.parse(JSON.stringify(response.data)); // Copia profunda
        this.loading = false;
      } catch (err) {
        this.loading = false;
        this.error = `Error cargando la configuración: ${err.message}`;
        console.error('Error cargando configuración:', err);
      }
    },
    
    async saveConfig() {
      this.saving = true;
      
      try {
        await axios.post('/api/config', this.config);
        this.originalConfig = JSON.parse(JSON.stringify(this.config)); // Actualizar original
        this.$toasted.success('Configuración guardada correctamente');
        this.saving = false;
      } catch (err) {
        this.saving = false;
        this.$toasted.error(`Error guardando la configuración: ${err.message}`);
        console.error('Error guardando configuración:', err);
      }
    },
    
    resetConfig() {
      if (confirm('¿Estás seguro de restablecer todos los cambios?')) {
        this.config = JSON.parse(JSON.stringify(this.originalConfig)); // Copia profunda
      }
    },
    
    addCamera() {
      this.editing = {
        id: `cam_${Date.now()}`,
        name: 'Nueva Cámara',
        enabled: true,
        vendor: 'generic',
        url: '',
        username: '',
        password: '',
        fps: 15,
        resolution: '1280x720',
        recording: {
          enabled: true,
          mode: 'motion',
          pre_record: 5,
          post_record: 10
        },
        zones: []
      };
      this.editingIndex = -1;
      this.showCameraModal = true;
    },
    
    editCamera(index) {
      this.editing = JSON.parse(JSON.stringify(this.config.cameras[index])); // Copia profunda
      this.editingIndex = index;
      this.showCameraModal = true;
    },
    
    saveCamera() {
      if (this.editingIndex === -1) {
        // Nueva cámara
        this.config.cameras.push(this.editing);
      } else {
        // Actualizar cámara existente
        this.config.cameras[this.editingIndex] = this.editing;
      }
      
      this.closeCameraModal();
    },
    
    removeCamera(index) {
      if (confirm(`¿Estás seguro de eliminar la cámara "${this.config.cameras[index].name}"?`)) {
        this.config.cameras.splice(index, 1);
      }
    },
    
    closeCameraModal() {
      this.showCameraModal = false;
      this.editing = null;
      this.editingIndex = -1;
    },
    
    addZone(cameraIndex) {
      this.editing = {
        name: 'Nueva Zona',
        type: 'intrusion',
        points: [[100, 100], [300, 100], [300, 300], [100, 300]],
        color: 'red',
        enabled: true
      };
      this.editingIndex = -1;
      this.editingParentIndex = cameraIndex;
      this.showZoneModal = true;
    },
    
    editZone(cameraIndex, zoneIndex) {
      this.editing = JSON.parse(JSON.stringify(this.config.cameras[cameraIndex].zones[zoneIndex]));
      this.editingIndex = zoneIndex;
      this.editingParentIndex = cameraIndex;
      this.showZoneModal = true;
    },
    
    saveZone() {
      if (this.editingIndex === -1) {
        // Nueva zona
        this.config.cameras[this.editingParentIndex].zones.push(this.editing);
      } else {
        // Actualizar zona existente
        this.config.cameras[this.editingParentIndex].zones[this.editingIndex] = this.editing;
      }
      
      this.closeZoneModal();
    },
    
    removeZone(cameraIndex, zoneIndex) {
      if (confirm(`¿Estás seguro de eliminar la zona "${this.config.cameras[cameraIndex].zones[zoneIndex].name}"?`)) {
        this.config.cameras[cameraIndex].zones.splice(zoneIndex, 1);
      }
    },
    
    closeZoneModal() {
      this.showZoneModal = false;
      this.editing = null;
      this.editingIndex = -1;
      this.editingParentIndex = -1;
    },
    
    addAgent() {
      this.editing = {
        type: 'custom',
        name: 'Nuevo Agente',
        enabled: true,
        model: '',
        confidence_threshold: 0.5,
        schedule: {
          enabled: false,
          time_ranges: []
        },
        params: {}
      };
      this.editingIndex = -1;
      this.showAgentModal = true;
    },
    
    editAgent(type, key) {
      this.editing = JSON.parse(JSON.stringify(this.config.agents[type]));
      this.editing.type = type;
      this.editing.key = key;
      this.editingIndex = type;
      this.showAgentModal = true;
    },
    
    saveAgent() {
      const { type, ...agentConfig } = this.editing;
      this.config.agents[type] = agentConfig;
      this.closeAgentModal();
    },
    
    closeAgentModal() {
      this.showAgentModal = false;
      this.editing = null;
      this.editingIndex = -1;
    }
  }
};
</script>

<style scoped>
.config-editor {
  padding: 1rem;
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.spinner {
  border: 5px solid #f3f3f3;
  border-top: 5px solid #3498db;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem;
  color: #721c24;
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 0.25rem;
}

.error-message i {
  font-size: 2rem;
  margin-bottom: 1rem;
}

.tab-content {
  background-color: white;
}
</style> 