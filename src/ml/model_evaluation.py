    # src/ml/model_evaluation.py
    from ultralytics import YOLO
    import numpy as np
    import matplotlib.pyplot as plt
    
    class ModelEvaluator:
        def __init__(self, model_path):
            self.model = YOLO(model_path)
        
        def evaluate_precision_recall(self, test_data):
            # Realizar evaluaciÃ³n de precisiÃ³n y recall
            metrics = self.model.val(data=test_data)
            
            # Graficar curva P-R
            precision = metrics.results_dict['metrics/precision(B)']
            recall = metrics.results_dict['metrics/recall(B)']
            
            plt.figure(figsize=(10, 6))
            plt.plot(recall, precision, 'b', label='Precision-Recall curve')
            plt.title('Precision-Recall Curve')
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.legend()
            plt.savefig('data/output/precision_recall_curve.png')
            
            return metrics
