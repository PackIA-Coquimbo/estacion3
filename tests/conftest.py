"""Configuración común de las pruebas (pytest)."""
import os
import sys

import cv2
import numpy as np
import pytest

CARPETA_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CARPETA_PROYECTO)

import clasificador_naranjas as cn  # noqa: E402

VIDEO_PRUEBA = os.path.join(CARPETA_PROYECTO, "video_prueba_cinta.mp4")
ZONA_PRUEBA = [551, 134, 1400, 1007]          # zona con la que se hizo el video de prueba
ESCALA_PRUEBA = 0.2915604662874815


def imagen_vacia():
    """Imagen 1920x1080 gris oscuro, sin naranjas."""
    return np.full((1080, 1920, 3), 40, np.uint8)


def procesar_video(motor, ruta=VIDEO_PRUEBA):
    cap = cv2.VideoCapture(ruta)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        motor.procesar(frame)
    cap.release()


@pytest.fixture
def motor_prueba(tmp_path, monkeypatch):
    """Motor que guarda lo que enviaría en motor.enviados, sin tocar los archivos del proyecto."""
    from motor_estacion3 import Motor
    monkeypatch.setattr(cn, "ARCHIVO_CONFIG", str(tmp_path / "configuracion.json"))
    enviados = []
    motor = Motor(enviar=lambda datos, destino: enviados.append((datos, destino)), carpeta=tmp_path)
    motor.enviados = enviados
    motor.usar_autocalibracion = False
    cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2 = ZONA_PRUEBA
    cn.ESCALA_FONDO = ESCALA_PRUEBA
    cn.CALIBRADO = True
    motor.fijar_direccion("derecha")
    motor.fijar_linea(0.6)
    return motor
