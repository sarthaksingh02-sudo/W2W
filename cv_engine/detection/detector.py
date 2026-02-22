from ultralytics import YOLO
import torch
import numpy as np

class ObjectDetector:
    def __init__(self, model_path="yolov8n.pt", device=0, conf_thres=0.3, iou_thres=0.45):
        """
        Inference Wrapper for YOLOv8 (GPU-accelerated, FP16).
        """
        # Hardware acceleration check
        self.device = f"cuda:{device}" if torch.cuda.is_available() and device != 'cpu' else 'cpu'
        self.model = YOLO(model_path)
        
        # Configuration
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.inference_size = 640
        self.classes = [0, 24, 26, 39, 41, 67] # Person, Backpack, Handbag, Bottle, Cup, Cell Phone

        # FP16 Warmup
        self.model.predict(
            np.zeros((self.inference_size, self.inference_size, 3), dtype=np.uint8), 
            device=self.device, 
            verbose=False,
            half=True
        )

    def detect(self, frame):
        """
        Run inference and return list of detections.
        """
        results = self.model.predict(
            frame,
            imgsz=self.inference_size,
            device=self.device,
            conf=self.conf_thres,
            iou=self.iou_thres,
            half=True, # FP16
            verbose=False,
            classes=self.classes
        )[0]

        detections = []
        if results.boxes:
            for box in results.boxes:
                # Format: [x1, y1, x2, y2, confidence, class_id]
                d = box.data[0].cpu().numpy().tolist()
                detections.append(d)
        
        return detections
