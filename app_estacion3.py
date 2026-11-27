"""
App de la Estación 3 (PackIA Coquimbo)
--------------------------------------
Junta en una sola página web, con 3 pestañas:
  1. Clasificador     (calibrar, elegir zona, fotos, medidas)
  2. Estación cinta   (línea de decisión, dirección, grabar, contadores)
  3. Simulador        (estaciones 4 y 5 simuladas)

Uso (con el venv activado):
    python3 app_estacion3.py                       -> cámara
    python3 app_estacion3.py video_prueba_cinta.mp4 -> probar con un video
Luego abrir en el navegador:  http://localhost:8000
(o desde otro computador del router: http://IP_DE_ESTE_EQUIPO:8000)
"""

import atexit
import logging
import socket
import sys
import threading
import time
import traceback

import cv2
from flask import Flask, Response, abort, jsonify, render_template, request

import clasificador_naranjas as cn
from motor_estacion3 import PUERTO, Motor
from simulador_web import estado_simulador, reiniciar_simulador, simulador

VISTAS = ("clasificador", "cinta", "mascara")
IMAGENES_POR_SEGUNDO_VIDEO = 15     # cuántas imágenes por segundo se mandan a la página


# ---------------- Cámara (hilo aparte) ----------------
def iniciar_camara(motor, fuente):
    """
    Lee la cámara (o el video) en un hilo aparte y le pasa cada imagen al motor.
    Funciona aunque nadie tenga la página abierta.
    """
    es_video = isinstance(fuente, str)

    def bucle():
        while True:
            cap = cv2.VideoCapture(fuente)
            if not cap.isOpened():
                motor.mensaje_fuente = f"No se pudo abrir la cámara {fuente}. Reintentando..."
                time.sleep(3)
                continue
            if not es_video:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, cn.ANCHO)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cn.ALTO)
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            espera = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 15) if es_video else 0
            motor.mensaje_fuente = ""
            while True:
                inicio = time.time()
                ok, frame = cap.read()
                if not ok:
                    break                       # fin del video (se repite) o cámara desconectada
                try:
                    motor.procesar(frame)
                except Exception as e:          # un error en una imagen no debe detener la estación
                    motor.ultimo_error_motor = f"{type(e).__name__}: {e}"
                    traceback.print_exc()
                    time.sleep(0.5)
                if espera:                      # un video se reproduce a su velocidad real
                    time.sleep(max(0, espera - (time.time() - inicio)))
            cap.release()
            if not es_video:
                motor.mensaje_fuente = "Se perdió la imagen de la cámara. Reintentando..."
                time.sleep(1)

    hilo = threading.Thread(target=bucle, daemon=True)
    hilo.start()
    return hilo


# ---------------- Servidor web ----------------
def crear_app(motor):
    app = Flask(__name__)
    app.register_blueprint(simulador)
    # No anotar cada petición en la terminal (la página pide el estado 3 veces por
    # segundo; en la Raspberry eso llenaría la tarjeta microSD con el registro).
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    def leer_json(*campos):
        """Datos JSON del botón; si falta algún campo responde 400."""
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict) or any(c not in datos for c in campos):
            abort(400, description=f"Faltan datos: {', '.join(campos)}")
        return datos

    def respuesta(ok, mensaje):
        return jsonify(ok=bool(ok), mensaje=mensaje)

    @app.errorhandler(400)
    def error_400(e):
        return jsonify(ok=False, mensaje=e.description), 400

    @app.route("/")
    def inicio():
        return render_template("index.html")

    @app.route("/video/<vista>")
    def video(vista):
        if vista not in VISTAS:
            abort(404)

        def imagenes():
            while True:
                jpeg = motor.dibujar(vista)
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                time.sleep(1.0 / IMAGENES_POR_SEGUNDO_VIDEO)

        return Response(imagenes(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/estado")
    def estado():
        datos = motor.estado()
        datos["simulador"] = estado_simulador()
        return jsonify(datos)

    @app.route("/api/calibrar", methods=["POST"])
    def calibrar():
        return respuesta(*motor.calibrar())

    @app.route("/api/zona", methods=["POST"])
    def zona():
        d = leer_json("x1", "y1", "x2", "y2")
        try:
            return respuesta(*motor.fijar_zona(d["x1"], d["y1"], d["x2"], d["y2"]))
        except (TypeError, ValueError):
            abort(400, description="La zona debe ser numérica")

    @app.route("/api/linea", methods=["POST"])
    def linea():
        d = leer_json("fraccion")
        try:
            return respuesta(*motor.fijar_linea(d["fraccion"]))
        except (TypeError, ValueError):
            abort(400, description="La línea debe ser un número entre 0 y 1")

    @app.route("/api/direccion", methods=["POST"])
    def direccion():
        return respuesta(*motor.fijar_direccion(leer_json("direccion")["direccion"]))

    @app.route("/api/urls", methods=["POST"])
    def urls():
        d = leer_json("url4", "url5")
        return respuesta(*motor.fijar_urls(d["url4"], d["url5"]))

    @app.route("/api/envio", methods=["POST"])
    def envio():
        activo = bool(leer_json("activo")["activo"])
        motor.fijar_envio(activo)
        return respuesta(True, "Envío a las estaciones activado" if activo else "Envío en pausa: no se envía ni se cuenta")

    @app.route("/api/simulador", methods=["POST"])
    def simulador_onoff():
        activo = bool(leer_json("activo")["activo"])
        motor.fijar_simulador(activo)
        if activo:
            reiniciar_simulador()
        return respuesta(True, "Simulador encendido: se envía a las estaciones simuladas" if activo
                         else "Simulador apagado: se envía a las estaciones reales")

    @app.route("/api/foto", methods=["POST"])
    def foto():
        ruta = motor.guardar_foto()
        return respuesta(bool(ruta), f"Foto guardada: {ruta}" if ruta else "Todavía no hay imagen de la cámara")

    @app.route("/api/grabar", methods=["POST"])
    def grabar():
        grabando = motor.alternar_grabacion()
        return respuesta(True, "Grabando video (carpeta videos/)" if grabando else "Grabación terminada")

    @app.route("/api/reiniciar", methods=["POST"])
    def reiniciar():
        motor.reiniciar()
        return respuesta(True, "Contadores reiniciados")

    return app


def ip_local():
    """IP de este equipo en la red (para abrir la app desde otro computador)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "IP_DE_ESTE_EQUIPO"


if __name__ == "__main__":
    fuente = cn.CAMARA
    if len(sys.argv) > 1:
        fuente = int(sys.argv[1]) if sys.argv[1].isdigit() else sys.argv[1]

    motor = Motor()
    atexit.register(motor.cerrar)       # si se cierra mientras graba, el video queda bien guardado
    iniciar_camara(motor, fuente)
    print(f"Abre en el navegador:  http://localhost:{PUERTO}")
    print(f"Desde otro computador: http://{ip_local()}:{PUERTO}")
    crear_app(motor).run(host="0.0.0.0", port=PUERTO, threaded=True)
