import os
import json
import logging
import shutil
import yaml
import mlflow
import mlflow.pytorch
from pathlib import Path
from ultralytics import YOLO
from datetime import datetime
from src.training.dataset_manager import DatasetManager

class ModelTrainer:
    def __init__(self, config_path="configs/training.json"):
        self.config = self._load_config(config_path)
        self.dataset_manager = DatasetManager()
        self.logger = logging.getLogger("ModelTrainer")
        
        # Configurar MLflow
        mlflow_tracking_uri = self.config.get("mlflow_tracking_uri", "mlruns")
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        
    def _load_config(self, config_path):
        """Carga la configuración de entrenamiento"""
        if not os.path.exists(config_path):
            self.logger.warning(f"Archivo de configuración no encontrado: {config_path}, usando valores por defecto")
            return {
                "default_epochs": 50,
                "default_batch_size": 16,
                "default_image_size": 640,
                "models_dir": "models",
                "exports_dir": "exports",
                "mlflow_tracking_uri": "mlruns",
                "mlflow_experiment_name": "vigia_model_training"
            }
            
        with open(config_path, 'r') as f:
            if config_path.endswith('.json'):
                return json.load(f)
            elif config_path.endswith('.yaml') or config_path.endswith('.yml'):
                return yaml.safe_load(f)
        
    def train_model(self, dataset_name, model_type="object_detection", 
                   base_model=None, epochs=None, batch_size=None, image_size=None):
        """Entrena un modelo con el dataset especificado"""
        # Validar dataset
        if dataset_name not in self.dataset_manager.datasets:
            raise ValueError(f"Dataset '{dataset_name}' no encontrado")
            
        # Usar valores predeterminados si no se especifican
        epochs = epochs or self.config.get("default_epochs", 50)
        batch_size = batch_size or self.config.get("default_batch_size", 16)
        image_size = image_size or self.config.get("default_image_size", 640)
        
        # Preparar dataset
        dataset_export_path = self.dataset_manager.export_dataset(dataset_name, format="yolo")
        dataset_yaml = os.path.join(dataset_export_path, "data.yaml")
        
        if not os.path.exists(dataset_yaml):
            raise FileNotFoundError(f"Archivo de configuración YOLO no encontrado: {dataset_yaml}")
        
        # Definir modelo base
        if not base_model:
            if model_type == "object_detection":
                base_model = "yolov8n.pt"  # Modelo más pequeño por defecto
            else:
                raise ValueError(f"Tipo de modelo no soportado: {model_type}")
        
        # Generar ID único para el modelo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_id = f"{dataset_name}_{model_type}_{timestamp}"
        
        # Crear directorio para el modelo si no existe
        models_dir = self.config.get("models_dir", "models")
        os.makedirs(models_dir, exist_ok=True)
        
        # Configurar MLflow
        mlflow.set_experiment(self.config.get("mlflow_experiment_name", "vigia_model_training"))
        
        # Entrenamiento con MLflow tracking
        with mlflow.start_run(run_name=model_id):
            self.logger.info(f"Iniciando entrenamiento: {model_id}")
            
            # Registrar parámetros
            mlflow.log_param("dataset", dataset_name)
            mlflow.log_param("model_type", model_type)
            mlflow.log_param("base_model", base_model)
            mlflow.log_param("epochs", epochs)
            mlflow.log_param("batch_size", batch_size)
            mlflow.log_param("image_size", image_size)
            
            try:
                # Cargar modelo base
                model = YOLO(base_model)
                
                # Entrenar modelo
                results = model.train(
                    data=dataset_yaml,
                    epochs=epochs,
                    batch=batch_size,
                    imgsz=image_size,
                    name=model_id
                )
                
                # Guardar modelo entrenado
                final_model_path = os.path.join(models_dir, f"{model_id}.pt")
                shutil.copy(results.model.path, final_model_path)
                
                # Registrar métricas
                metrics = results.results_dict
                for metric_name, metric_value in metrics.items():
                    if isinstance(metric_value, (int, float)):
                        mlflow.log_metric(metric_name, metric_value)
                
                # Registrar modelo en MLflow
                mlflow.pytorch.log_model(model.model, "model")
                
                # Registrar artefactos adicionales (gráficos, etc.)
                for plot_name in ["confusion_matrix.png", "results.png", "PR_curve.png"]:
                    plot_path = os.path.join("runs/detect", model_id, plot_name)
                    if os.path.exists(plot_path):
                        mlflow.log_artifact(plot_path, "plots")
                
                self.logger.info(f"Entrenamiento completado: {model_id}")
                return {
                    "model_id": model_id,
                    "model_path": final_model_path,
                    "metrics": metrics
                }
                
            except Exception as e:
                self.logger.error(f"Error durante el entrenamiento: {e}")
                mlflow.log_param("error", str(e))
                raise
    
    def export_model(self, model_id, format="onnx"):
        """Exporta modelo entrenado para producción"""
        models_dir = self.config.get("models_dir", "models")
        model_path = os.path.join(models_dir, f"{model_id}.pt")
        
        if not os.path.exists(model_path):
            raise ValueError(f"Modelo {model_id} no existe en {model_path}")
        
        exports_dir = self.config.get("exports_dir", "exports")
        export_path = os.path.join(exports_dir, model_id)
        os.makedirs(export_path, exist_ok=True)
        
        if format.lower() == "onnx":
            # Exportar a formato ONNX
            output_path = os.path.join(export_path, f"{model_id}.onnx")
            
            # Cargar el modelo
            model = YOLO(model_path)
            
            # Exportar a ONNX
            success = model.export(format="onnx", output=output_path)
            
            if success:
                self.logger.info(f"Modelo exportado exitosamente a ONNX: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"Error al exportar modelo {model_id} a formato ONNX")
        
        elif format.lower() == "tflite":
            # Exportar a formato TFLite
            output_path = os.path.join(export_path, f"{model_id}.tflite")
            
            # Cargar el modelo
            model = YOLO(model_path)
            
            # Exportar a TFLite
            success = model.export(format="tflite", output=output_path)
            
            if success:
                self.logger.info(f"Modelo exportado exitosamente a TFLite: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"Error al exportar modelo {model_id} a formato TFLite")
        
        else:
            raise ValueError(f"Formato de exportación no soportado: {format}") 