import os
import json
import shutil
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path

class DatasetManager:
    def __init__(self, base_path="data/custom_datasets"):
        self.base_path = base_path
        self.datasets = self._discover_datasets()
        
    def _discover_datasets(self):
        """Encuentra datasets existentes en el directorio base"""
        datasets = {}
        if os.path.exists(self.base_path):
            for dataset_name in os.listdir(self.base_path):
                dataset_path = os.path.join(self.base_path, dataset_name)
                if os.path.isdir(dataset_path):
                    # Verificar archivo de metadatos
                    metadata_path = os.path.join(dataset_path, "metadata.json")
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        datasets[dataset_name] = metadata
        return datasets
        
    def create_dataset(self, name, description=None):
        """Crea estructura para un nuevo dataset"""
        dataset_path = os.path.join(self.base_path, name)
        
        if os.path.exists(dataset_path):
            raise ValueError(f"El dataset '{name}' ya existe")
            
        # Crear directorios
        os.makedirs(dataset_path, exist_ok=True)
        os.makedirs(os.path.join(dataset_path, "images"), exist_ok=True)
        os.makedirs(os.path.join(dataset_path, "labels"), exist_ok=True)
        
        # Crear metadatos
        metadata = {
            "name": name,
            "description": description or "",
            "created": datetime.now().isoformat(),
            "samples_count": 0,
            "classes": {}
        }
        
        with open(os.path.join(dataset_path, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Actualizar caché de datasets
        self.datasets[name] = metadata
        
        return name
        
    def add_sample(self, dataset_name, image_data, annotations=None):
        """Añade muestra al dataset con anotaciones opcionales"""
        if dataset_name not in self.datasets:
            raise ValueError(f"El dataset '{dataset_name}' no existe")
            
        dataset_path = os.path.join(self.base_path, dataset_name)
        metadata = self.datasets[dataset_name]
        
        # Generar ID de muestra
        sample_id = f"{dataset_name}_{metadata['samples_count'] + 1:06d}"
        
        # Guardar imagen
        image_path = os.path.join(dataset_path, "images", f"{sample_id}.jpg")
        cv2.imwrite(image_path, image_data)
        
        # Guardar anotaciones si se proporcionaron
        if annotations:
            label_path = os.path.join(dataset_path, "labels", f"{sample_id}.txt")
            
            with open(label_path, 'w') as f:
                for annotation in annotations:
                    # Actualizar estadísticas de clase
                    class_id = annotation["class_id"]
                    if str(class_id) not in metadata["classes"]:
                        metadata["classes"][str(class_id)] = {
                            "name": annotation.get("class_name", f"class_{class_id}"),
                            "count": 0
                        }
                    metadata["classes"][str(class_id)]["count"] += 1
                    
                    # Escribir anotación en formato YOLO: class_id x_center y_center width height
                    # Convertir de coordenadas absolutas a relativas (0-1)
                    height, width = image_data.shape[:2]
                    x, y, w, h = annotation["bbox"]
                    x_center = (x + w/2) / width
                    y_center = (y + h/2) / height
                    w_rel = w / width
                    h_rel = h / height
                    
                    f.write(f"{class_id} {x_center} {y_center} {w_rel} {h_rel}\n")
        
        # Actualizar metadatos
        metadata["samples_count"] += 1
        with open(os.path.join(dataset_path, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return sample_id
    
    def export_dataset(self, dataset_name, format="yolo"):
        """Exporta dataset en formato compatible con entrenamiento"""
        if dataset_name not in self.datasets:
            raise ValueError(f"El dataset '{dataset_name}' no existe")
            
        dataset_path = os.path.join(self.base_path, dataset_name)
        export_path = os.path.join(self.base_path, f"{dataset_name}_export")
        
        # Crear directorio de exportación
        os.makedirs(export_path, exist_ok=True)
        
        if format.lower() == "yolo":
            # Para YOLO, la estructura ya está correcta, solo necesitamos
            # copiar archivos y crear data.yaml
            
            # Copiar imágenes y etiquetas
            os.makedirs(os.path.join(export_path, "images", "train"), exist_ok=True)
            os.makedirs(os.path.join(export_path, "labels", "train"), exist_ok=True)
            
            # Copiar todas las imágenes y etiquetas
            for filename in os.listdir(os.path.join(dataset_path, "images")):
                shutil.copy(
                    os.path.join(dataset_path, "images", filename),
                    os.path.join(export_path, "images", "train", filename)
                )
                
            for filename in os.listdir(os.path.join(dataset_path, "labels")):
                shutil.copy(
                    os.path.join(dataset_path, "labels", filename),
                    os.path.join(export_path, "labels", "train", filename)
                )
            
            # Crear data.yaml para entrenamiento YOLO
            metadata = self.datasets[dataset_name]
            classes = []
            for class_id in sorted(metadata["classes"].keys(), key=int):
                classes.append(metadata["classes"][class_id]["name"])
                
            yaml_content = {
                "path": os.path.abspath(export_path),
                "train": "images/train",
                "val": "images/train",  # Mismo conjunto para simplificar
                "nc": len(classes),
                "names": classes
            }
            
            with open(os.path.join(export_path, "data.yaml"), 'w') as f:
                # Formato YAML manual simple
                f.write(f"path: {yaml_content['path']}\n")
                f.write(f"train: {yaml_content['train']}\n")
                f.write(f"val: {yaml_content['val']}\n")
                f.write(f"nc: {yaml_content['nc']}\n")
                f.write("names:\n")
                for name in yaml_content["names"]:
                    f.write(f"  - '{name}'\n")
            
            return export_path
            
        elif format.lower() == "coco":
            # Implementar exportación a formato COCO JSON
            # (Implementación simplificada)
            coco_data = {
                "info": {
                    "description": self.datasets[dataset_name].get("description", ""),
                    "date_created": datetime.now().isoformat()
                },
                "images": [],
                "annotations": [],
                "categories": []
            }
            
            # Llenar categorías
            for class_id, class_info in self.datasets[dataset_name]["classes"].items():
                coco_data["categories"].append({
                    "id": int(class_id),
                    "name": class_info["name"],
                    "supercategory": "object"
                })
            
            # Implementar resto de conversión COCO
            # ...
            
            with open(os.path.join(export_path, "annotations.json"), 'w') as f:
                json.dump(coco_data, f, indent=2)
                
            return export_path
            
        else:
            raise ValueError(f"Formato de exportación no soportado: {format}")
    
    def get_dataset_info(self, dataset_name):
        """Obtiene información del dataset"""
        if dataset_name not in self.datasets:
            raise ValueError(f"El dataset '{dataset_name}' no existe")
        return self.datasets[dataset_name]
    
    def delete_dataset(self, dataset_name):
        """Elimina un dataset completo"""
        if dataset_name not in self.datasets:
            raise ValueError(f"El dataset '{dataset_name}' no existe")
            
        dataset_path = os.path.join(self.base_path, dataset_name)
        shutil.rmtree(dataset_path)
        del self.datasets[dataset_name]
        return True 