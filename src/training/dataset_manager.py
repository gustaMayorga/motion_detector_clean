class DatasetManager:
    def __init__(self, base_path="data/custom_datasets"):
        self.base_path = base_path
        self.datasets = self._discover_datasets()
        
    def _discover_datasets(self):
        # Encontrar datasets existentes
        # ...
        
    def create_dataset(self, name, description=None):
        # Crear estructura para nuevo dataset
        # ...
        
    def add_sample(self, dataset_name, image_data, annotations=None):
        # Añadir muestra al dataset con anotaciones opcionales
        # ...
        
    def export_dataset(self, dataset_name, format="yolo"):
        # Exportar dataset en formato compatible con entrenamiento
        # ... 