"""
Mide cuántas imágenes por segundo procesa cada detector.
Sirve para saber si la Raspberry Pi alcanza a seguir la cinta.

Uso:  python3 medir_velocidad.py
"""
import os
import time

import cv2

import clasificador_naranjas as cn

REPETICIONES = 30


def medir(nombre, funcion, imagenes):
    funcion(imagenes[0])                       # la primera vez carga el modelo; no se cuenta
    inicio = time.time()
    for i in range(REPETICIONES):
        funcion(imagenes[i % len(imagenes)])
    t = (time.time() - inicio) / REPETICIONES
    print(f"{nombre:35s} {t * 1000:7.1f} ms por imagen  ->  {1 / t:5.1f} imágenes por segundo")


if __name__ == "__main__":
    cn.cargar_configuracion()
    nombres = sorted(os.listdir(cn.CARPETA_FOTOS))[-10:]
    imagenes = [cv2.imread(os.path.join(cn.CARPETA_FOTOS, n)) for n in nombres]

    medir("Detector por color", cn.buscar_naranjas_color, imagenes)

    from ultralytics import YOLO
    for nombre_modelo, dispositivo in [("best.pt", "cpu"), ("best_ncnn_model", "cpu")]:
        if not os.path.exists(nombre_modelo):
            print(f"(no existe {nombre_modelo}; se omite)")
            continue
        cn.modelo_yolo = YOLO(nombre_modelo, task="segment")

        def yolo(frame, d=dispositivo):
            recorte = frame[cn.ZONA_Y1:cn.ZONA_Y2, cn.ZONA_X1:cn.ZONA_X2]
            cn.modelo_yolo.predict(recorte, conf=cn.CONFIANZA_YOLO, retina_masks=True,
                                   device=d, verbose=False)

        medir(f"YOLO {nombre_modelo} ({dispositivo})", yolo, imagenes)
