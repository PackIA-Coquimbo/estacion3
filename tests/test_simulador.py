"""Pruebas del simulador de las estaciones 4 y 5 dentro de la app."""
import pytest
from flask import Flask

from simulador_web import estado_simulador, reiniciar_simulador, simulador


@pytest.fixture
def cliente():
    app = Flask(__name__)
    app.register_blueprint(simulador)
    reiniciar_simulador()
    return app.test_client()


def test_estacion4_mueve_servo(cliente):
    assert cliente.post("/sim/estacion4/fruta", json={"id": 1, "calibre": "grande"}).status_code == 200
    e = estado_simulador()["estacion4"]
    assert e["recibidas"] == 1
    assert e["servo"] == "derecha"


def test_estacion5_cuenta(cliente):
    for c in ["chico", "mediano", "mediano"]:
        cliente.post("/sim/estacion5/fruta", json={"id": 1, "calibre": c})
    assert estado_simulador()["estacion5"] == {"total": 3, "chico": 1, "mediano": 2, "grande": 0, "revision": 0}


def test_json_invalido_es_400(cliente):
    assert cliente.post("/sim/estacion4/fruta", data="hola").status_code == 400
