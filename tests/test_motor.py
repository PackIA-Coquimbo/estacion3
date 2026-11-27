"""Pruebas del motor de la app (motor_estacion3.py)."""
import cv2
import numpy as np

from conftest import imagen_vacia, procesar_video


def test_video_envia_tres_naranjas_en_orden(motor_prueba):
    procesar_video(motor_prueba)
    a_estacion4 = [d["calibre"] for d, destino in motor_prueba.enviados if destino == "estacion4"]
    assert a_estacion4 == ["chico", "grande", "mediano"]
    assert motor_prueba.estado()["conteo"] == {"chico": 1, "mediano": 1, "grande": 1, "revision": 0, "total": 3}
    assert len([1 for d, destino in motor_prueba.enviados if destino == "estacion5"]) == 3


def test_envio_pausado_no_envia_ni_cuenta(motor_prueba):
    motor_prueba.fijar_envio(False)
    procesar_video(motor_prueba)
    assert motor_prueba.enviados == []
    assert motor_prueba.estado()["conteo"]["total"] == 0


def test_calibrar_sin_una_sola_naranja_no_cambia_escala(motor_prueba):
    escala = motor_prueba.estado()["escala"]
    motor_prueba.procesar(imagen_vacia())
    ok, mensaje = motor_prueba.calibrar()
    assert not ok
    assert "0" in mensaje
    assert motor_prueba.estado()["escala"] == escala


def test_fijar_zona_normaliza_y_rechaza(motor_prueba):
    assert motor_prueba.fijar_zona(1400, 1007, 551, 134)[0] is True
    assert motor_prueba.estado()["zona"] == [551, 134, 1400, 1007]
    assert motor_prueba.fijar_zona(100, 100, 150, 150)[0] is False      # menos de 100 px
    assert motor_prueba.fijar_zona(0, 0, 2500, 900)[0] is False         # fuera de la imagen
    assert motor_prueba.estado()["zona"] == [551, 134, 1400, 1007]


def test_fijar_linea_y_direccion_validan(motor_prueba):
    assert motor_prueba.fijar_linea(0.77)[0]
    assert not motor_prueba.fijar_linea(1.5)[0]
    assert motor_prueba.fijar_direccion("abajo")[0]
    assert not motor_prueba.fijar_direccion("diagonal")[0]
    assert motor_prueba.estado()["direccion"] == "abajo"


def test_configuracion_cinta_persiste(tmp_path):
    from motor_estacion3 import Motor
    m = Motor(enviar=lambda d, dest: None, carpeta=tmp_path)
    m.fijar_direccion("abajo")
    m.fijar_linea(0.77)
    otro = Motor(enviar=lambda d, dest: None, carpeta=tmp_path)
    assert otro.estado()["direccion"] == "abajo"
    assert otro.estado()["posicion_linea"] == 0.77


def test_url_segun_simulador(motor_prueba):
    motor_prueba.fijar_urls("http://10.0.0.4:5004/fruta", "http://10.0.0.5:5005/fruta")
    motor_prueba.fijar_simulador(True)
    assert motor_prueba.url_estacion("estacion4") == "http://127.0.0.1:8000/sim/estacion4/fruta"
    motor_prueba.fijar_simulador(False)
    assert motor_prueba.url_estacion("estacion5") == "http://10.0.0.5:5005/fruta"


def test_dibujar_devuelve_jpeg_de_960(motor_prueba):
    motor_prueba.procesar(imagen_vacia())
    for vista in ("clasificador", "cinta", "mascara"):
        img = cv2.imdecode(np.frombuffer(motor_prueba.dibujar(vista), np.uint8), 1)
        assert img.shape[1] == 960
