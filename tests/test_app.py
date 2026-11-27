"""Pruebas del servidor de la app (app_estacion3.py), sin cámara."""
import pytest

from app_estacion3 import crear_app


@pytest.fixture
def motor_app(motor_prueba):
    return motor_prueba


@pytest.fixture
def cliente(motor_app):
    return crear_app(motor_app).test_client()


def test_estado_tiene_claves(cliente):
    datos = cliente.get("/api/estado").get_json()
    assert {"conteo", "zona", "direccion", "simulador", "envio_activo"} <= set(datos)


def test_linea_y_direccion(cliente):
    assert cliente.post("/api/linea", json={"fraccion": 0.5}).get_json()["ok"]
    assert cliente.post("/api/direccion", json={"direccion": "diagonal"}).get_json()["ok"] is False


def test_zona_sin_datos_es_400(cliente):
    assert cliente.post("/api/zona", json={"x1": 10}).status_code == 400


def test_video_vista_invalida_es_404(cliente):
    assert cliente.get("/video/otra").status_code == 404


def test_simulador_recibe_envio_del_motor(cliente, motor_app):
    cliente.post("/api/simulador", json={"activo": True})
    assert motor_app.url_estacion("estacion4").endswith("/sim/estacion4/fruta")
