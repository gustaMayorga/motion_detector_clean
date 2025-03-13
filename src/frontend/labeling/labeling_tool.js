class LabelingTool {
    constructor(containerId, datasetApi) {
        this.container = document.getElementById(containerId);
        this.api = datasetApi;
        this.currentImage = null;
        this.annotations = [];
        this.initialize();
    }
    
    initialize() {
        // Configurar interfaz de etiquetado
        // ...
    }
    
    loadImage(imageId) {
        // Cargar imagen para etiquetado
        // ...
    }
    
    createAnnotation(type, coords) {
        // Crear nueva anotación (bbox, polígono, etc)
        // ...
    }
    
    saveAnnotations() {
        // Guardar anotaciones actuales via API
        // ...
    }
} 