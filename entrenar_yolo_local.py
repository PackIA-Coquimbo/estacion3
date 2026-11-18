"""
Entrena YOLO directamente en el Mac (usa la GPU del chip Apple, "mps").
Antes: python3 generar_dataset.py   (crea la carpeta dataset_naranjas)
Uso:   python3 entrenar_yolo_local.py
Al terminar copia el modelo nuevo como best.pt (el anterior queda como best_anterior.pt).
"""
import os
import shutil
from ultralytics import YOLO

CARPETA = os.path.abspath("dataset_naranjas")

# data.yaml con la ruta completa del dataset
with open(os.path.join(CARPETA, "data.yaml"), "w") as f:
    f.write(f"path: {CARPETA}\ntrain: images/train\nval: images/val\nnames:\n  0: naranja\n")

modelo = YOLO("yolo26n-seg.pt")     # se descarga solo la primera vez
modelo.train(
    data=os.path.join(CARPETA, "data.yaml"),
    epochs=100,
    imgsz=640,
    batch=8,
    patience=0,
    flipud=0.5,      # la cámara mira desde arriba
    degrees=180,
    device="mps",    # GPU del Mac
    project="runs",
    name="naranjas",
    exist_ok=True,
)

# ruta real donde YOLO guardó el entrenamiento
nuevo = os.path.join(str(modelo.trainer.save_dir), "weights", "best.pt")
if os.path.exists("best.pt"):
    shutil.copy("best.pt", "best_anterior.pt")
shutil.copy(nuevo, "best.pt")
print("Listo: modelo nuevo guardado como best.pt (el anterior en best_anterior.pt)")
