"""Pruebas de las correcciones de la revisión final."""
import logging
import os
import threading
import time

import cv2
import numpy as np

from conftest import VIDEO_PRUEBA, imagen_vacia, procesar_video


def imagen_con_una_naranja():
    """Imagen gris con un círculo naranjo de ~212 px dentro de la zona de prueba."""
    img = imagen_vacia()
    cv2.circle(img, (975, 570), 106, (0, 128, 255), -1)
    return img


def test_grabacion_se_abre_y_cierra_en_el_hilo_de_la_camara(motor_prueba):
    motor_prueba.procesar(imagen_vacia())
    assert motor_prueba.alternar_grabacion() is True
    assert motor_prueba.grabador is None              # todavía no: lo abre procesar()
    motor_prueba.procesar(imagen_vacia())
    assert motor_prueba.grabador is not None
    assert motor_prueba.estado()["grabando"] is True
    assert motor_prueba.alternar_grabacion() is False
    assert motor_prueba.grabador is not None          # no se cierra desde el hilo de la página
    motor_prueba.procesar(imagen_vacia())
    assert motor_prueba.grabador is None
    videos = os.listdir(os.path.join(motor_prueba.carpeta, "videos"))
    assert len(videos) == 1


def test_error_al_procesar_no_detiene_la_camara(motor_prueba):
    from app_estacion3 import iniciar_camara
    llamadas = []
    original = motor_prueba.procesar

    def procesar_con_falla(frame):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("falla de prueba")
        original(frame)

    motor_prueba.procesar = procesar_con_falla
    iniciar_camara(motor_prueba, VIDEO_PRUEBA)
    time.sleep(1.5)
    assert len(llamadas) > 3
    assert "falla de prueba" in motor_prueba.ultimo_error_motor


def test_fps_cero_si_la_imagen_esta_detenida(motor_prueba):
    ahora = time.time()
    motor_prueba.tiempos = [ahora - 10, ahora - 9.9, ahora - 9.8]
    estado = motor_prueba.estado()
    assert estado["fps"] == 0
    assert estado["imagen_detenida"] is True


def test_mover_la_linea_no_reenvia_naranjas(motor_prueba):
    motor_prueba.fijar_linea(0.4)
    cap = cv2.VideoCapture(VIDEO_PRUEBA)
    movida = False
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        motor_prueba.procesar(frame)
        if not movida and motor_prueba.enviados:
            motor_prueba.fijar_linea(0.8)             # se mueve la línea con la cinta andando
            movida = True
    a_estacion4 = [d["calibre"] for d, destino in motor_prueba.enviados if destino == "estacion4"]
    assert len(a_estacion4) == 3


def test_calibrar_dos_veces_seguidas_funciona(motor_prueba, monkeypatch):
    motor_prueba.procesar(imagen_con_una_naranja())
    ok1, mensaje1 = motor_prueba.calibrar()
    ok2, mensaje2 = motor_prueba.calibrar()
    assert ok1, mensaje1
    assert ok2, mensaje2


def test_registro_de_peticiones_silenciado(motor_prueba):
    from app_estacion3 import crear_app
    crear_app(motor_prueba)
    assert logging.getLogger("werkzeug").level >= logging.WARNING
