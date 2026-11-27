"""
Simulador de las estaciones 4 y 5 dentro de la app (pestaña "Simulador")
------------------------------------------------------------------------
Hace lo mismo que simulador_estaciones.py, pero como parte de la app:
  POST /sim/estacion4/fruta  -> muestra hacia dónde movería el servo
  POST /sim/estacion5/fruta  -> lleva los contadores del dashboard
"""

import threading
from datetime import datetime

from flask import Blueprint, jsonify, request

simulador = Blueprint("simulador", __name__)

# Posición del servo para cada calibre (igual que simulador_estaciones.py)
SERVO = {"chico": "izquierda", "mediano": "centro", "grande": "derecha", "revision": "sin mover"}
MAXIMO_REGISTRO = 30

candado = threading.Lock()
datos = {}


def reiniciar_simulador():
    with candado:
        datos.clear()
        datos["estacion4"] = {"recibidas": 0, "ultima": None, "servo": "-"}
        datos["estacion5"] = {"total": 0, "chico": 0, "mediano": 0, "grande": 0, "revision": 0}
        datos["registro"] = []


def estado_simulador():
    with candado:
        return {
            "estacion4": dict(datos["estacion4"]),
            "estacion5": dict(datos["estacion5"]),
            "registro": list(datos["registro"]),
        }


def _anotar(texto):
    hora = datetime.now().strftime("%H:%M:%S")
    datos["registro"] = ([f"{hora}  {texto}"] + datos["registro"])[:MAXIMO_REGISTRO]


def _leer_fruta():
    """El JSON recibido, o None si no trae un calibre."""
    fruta = request.get_json(silent=True)
    if not isinstance(fruta, dict) or "calibre" not in fruta:
        return None
    return fruta


@simulador.route("/sim/estacion4/fruta", methods=["POST"])
def recibir_estacion4():
    fruta = _leer_fruta()
    if fruta is None:
        return jsonify(ok=False, mensaje="Se esperaba un JSON con 'calibre'"), 400
    servo = SERVO.get(fruta["calibre"], "?")
    with candado:
        e = datos["estacion4"]
        e["recibidas"] += 1
        e["ultima"] = fruta
        e["servo"] = servo
        _anotar(f"Estación 4: fruta {fruta.get('id', '?')} {fruta['calibre']} -> servo {servo}")
    return jsonify(ok=True)


@simulador.route("/sim/estacion5/fruta", methods=["POST"])
def recibir_estacion5():
    fruta = _leer_fruta()
    if fruta is None:
        return jsonify(ok=False, mensaje="Se esperaba un JSON con 'calibre'"), 400
    with candado:
        e = datos["estacion5"]
        e["total"] += 1
        e[fruta["calibre"]] = e.get(fruta["calibre"], 0) + 1
        _anotar(f"Estación 5: total {e['total']}")
    return jsonify(ok=True)


reiniciar_simulador()
