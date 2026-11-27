"""
Motor de la app de la Estación 3
--------------------------------
Hace todo el trabajo con cada imagen de la cámara, UNA sola vez:
detectar y medir las naranjas, seguirlas en la cinta, decidir el calibre
al cruzar la línea, enviar a las estaciones 4 y 5, autocalibrar y grabar.

La página web (app_estacion3.py) solo le pide al motor:
  - las imágenes dibujadas de cada pestaña (dibujar)
  - el estado actual (estado)
  - que haga acciones (calibrar, fijar_zona, fijar_linea, ...)

Reutiliza las funciones de clasificador_naranjas.py, estacion3_cinta.py y
autocalibracion.py, así la lógica es la misma que en esos programas.
"""

import json
import os
import threading
import time
import warnings
from datetime import datetime

import cv2
import numpy as np
warnings.filterwarnings("ignore", message="urllib3 v2")   # aviso inofensivo del Python del Mac
import requests

import clasificador_naranjas as cn
import estacion3_cinta as ec
import autocalibracion as ac

PUERTO = 8000                                   # puerto de la app
DIRECCIONES = ("abajo", "arriba", "derecha", "izquierda")
ARCHIVO_CONFIG_CINTA = "configuracion_cinta.json"
TAMANO_MINIMO_ZONA = 100                        # px por lado
MAXIMO_ULTIMAS = 10                             # naranjas recientes que se muestran


class Motor:
    def __init__(self, enviar=None, carpeta="."):
        """
        enviar(datos, destino): función que manda un mensaje a "estacion4" o
        "estacion5". Si no se entrega, se envía por HTTP (en segundo plano).
        carpeta: donde se guardan configuracion_cinta.json, fotos/ y videos/.
        """
        self.carpeta = str(carpeta)
        self.enviar = enviar if enviar is not None else self._enviar_http
        self.candado = threading.Lock()      # protege la última imagen y los datos compartidos

        # Ajustes (se guardan en configuracion_cinta.json)
        self.direccion = ec.DIRECCION
        self.posicion_linea = ec.POSICION_LINEA
        self.url_estacion4 = ec.URL_ESTACION4
        self.url_estacion5 = ec.URL_ESTACION5
        self.simulador_activo = False
        self.usar_autocalibracion = True
        self.envio_activo = True
        cn.cargar_configuracion()            # zona y escala (configuracion.json)
        self._cargar_config_cinta()

        # Estado del procesamiento
        self.seguidas = []
        self.siguiente_id = 1
        self.conteo = {"chico": 0, "mediano": 0, "grande": 0, "revision": 0}
        self.ultimas = []
        self.imagen = None                   # última imagen de la cámara (limpia)
        self.mascara = None
        self.naranjas = []                   # naranjas detectadas en la última imagen
        self.esquinas_marcador = None
        self.tiempos = []                    # momentos de las últimas imágenes (para img/s)
        self.grabador = None                 # cv2.VideoWriter (solo lo toca el hilo de la cámara)
        self.quiere_grabar = False           # lo que pidió el botón Grabar / Detener
        self.ultimo_error_motor = ""         # último error al procesar una imagen
        self.errores_envio = 0
        self.ultimo_error = ""
        self.mensaje_fuente = ""             # aviso si la cámara no abre, etc.

    # ---------------- Configuración ----------------
    def _ruta(self, nombre):
        return os.path.join(self.carpeta, nombre)

    def _cargar_config_cinta(self):
        ruta = self._ruta(ARCHIVO_CONFIG_CINTA)
        if os.path.exists(ruta):
            with open(ruta) as f:
                datos = json.load(f)
            self.direccion = datos.get("direccion", self.direccion)
            self.posicion_linea = datos.get("posicion_linea", self.posicion_linea)
            self.url_estacion4 = datos.get("url_estacion4", self.url_estacion4)
            self.url_estacion5 = datos.get("url_estacion5", self.url_estacion5)
            self.simulador_activo = datos.get("simulador_activo", self.simulador_activo)
            self.usar_autocalibracion = datos.get("usar_autocalibracion", self.usar_autocalibracion)
        ec.DIRECCION = self.direccion
        ec.POSICION_LINEA = self.posicion_linea

    def _guardar_config_cinta(self):
        datos = {
            "direccion": self.direccion,
            "posicion_linea": self.posicion_linea,
            "url_estacion4": self.url_estacion4,
            "url_estacion5": self.url_estacion5,
            "simulador_activo": self.simulador_activo,
            "usar_autocalibracion": self.usar_autocalibracion,
        }
        with open(self._ruta(ARCHIVO_CONFIG_CINTA), "w") as f:
            json.dump(datos, f, indent=2)

    # ---------------- Envío a las estaciones ----------------
    def url_estacion(self, destino):
        """Dirección a la que se envía: el simulador de la app o la estación real."""
        if self.simulador_activo:
            return f"http://127.0.0.1:{PUERTO}/sim/{destino}/fruta"
        return self.url_estacion4 if destino == "estacion4" else self.url_estacion5

    def _enviar_http(self, datos, destino):
        """Envía en segundo plano, para que la cámara nunca espere a la red."""
        def tarea():
            url = self.url_estacion(destino)
            try:
                r = requests.post(url, json=datos, timeout=ec.TIEMPO_ESPERA_HTTP)
                if r.status_code != 200:
                    raise requests.exceptions.RequestException(f"respondió {r.status_code}")
            except requests.exceptions.RequestException as e:
                self.errores_envio += 1
                self.ultimo_error = f"{destino} ({url}): {e}"
        threading.Thread(target=tarea, daemon=True).start()

    # ---------------- Procesar una imagen ----------------
    def procesar(self, frame):
        """Se llama con cada imagen de la cámara o del video."""
        self._actualizar_grabacion(frame)
        if self.grabador is not None:
            self.grabador.write(frame)
        esquinas = ac.revisar(frame) if self.usar_autocalibracion else None

        mascara, naranjas = cn.buscar_naranjas(frame)
        linea = ec.calcular_linea()

        with self.candado:
            self.siguiente_id = ec.actualizar_seguimiento(self.seguidas, naranjas, self.siguiente_id)
            for fruta in self.seguidas:
                n = fruta["encontrada"]
                if n is None:
                    continue
                anterior, actual = ec.avance(fruta), ec.avance(n)
                if not fruta["enviada"] and n["completa"] and ec.antes_de_la_linea(actual, linea):
                    fruta["medidas"].append(cn.diametro_en_mm(n["largo_px"], n["acostada"]))
                if not fruta["enviada"] and not fruta["nueva"] and ec.cruzo_la_linea(anterior, actual, linea):
                    self._decidir(fruta)
                fruta["x"], fruta["y"] = n["x"], n["y"]
                fruta["nueva"] = False

            self.imagen = frame
            self.mascara = mascara
            self.naranjas = naranjas
            if esquinas is not None or not self.usar_autocalibracion:
                self.esquinas_marcador = esquinas
            ahora = time.time()
            self.tiempos = (self.tiempos + [ahora])[-30:]

    def _decidir(self, fruta):
        """La fruta cruzó la línea: calibre final, envío y conteo (si el envío está activo)."""
        calibre, diametro = ec.decidir(fruta)
        fruta["enviada"] = True
        fruta["calibre"] = calibre
        if not self.envio_activo:
            fruta["calibre"] = calibre + " (pausa)"
            return
        datos = {
            "estacion": 3,
            "id": fruta["id"],
            "calibre": calibre,
            "diametro_mm": None if diametro is None else round(diametro, 1),
            "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.enviar(datos, "estacion4")
        self.enviar(datos, "estacion5")
        self.conteo[calibre] += 1
        self.ultimas = ([datos] + self.ultimas)[:MAXIMO_ULTIMAS]
        self._guardar_registro(datos)

    def _guardar_registro(self, datos):
        ruta_anterior = ec.ARCHIVO_REGISTRO
        ec.ARCHIVO_REGISTRO = self._ruta("registro_frutas.csv")
        try:
            ec.guardar_registro(datos)
        finally:
            ec.ARCHIVO_REGISTRO = ruta_anterior

    # ---------------- Dibujar las vistas ----------------
    def dibujar(self, vista, ancho=960):
        """Imagen JPEG (bytes) de la vista pedida: "clasificador", "cinta" o "mascara"."""
        with self.candado:
            imagen = None if self.imagen is None else self.imagen.copy()
            mascara = None if self.mascara is None else self.mascara.copy()
            naranjas = list(self.naranjas)
            seguidas = [dict(f) for f in self.seguidas]
            esquinas = self.esquinas_marcador

        if imagen is None:
            imagen = np.zeros((cn.ALTO, cn.ANCHO, 3), np.uint8)
            cv2.putText(imagen, self.mensaje_fuente or "Esperando la camara...", (60, 540),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        elif vista == "mascara":
            imagen = cv2.cvtColor(mascara, cv2.COLOR_GRAY2BGR)
        elif vista == "clasificador":
            self._dibujar_clasificador(imagen, naranjas, esquinas)
        else:
            self._dibujar_cinta(imagen, seguidas, esquinas)

        alto = int(imagen.shape[0] * ancho / imagen.shape[1])
        chica = cv2.resize(imagen, (ancho, alto), interpolation=cv2.INTER_AREA)
        _, jpeg = cv2.imencode(".jpg", chica, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes()

    def _dibujar_zona_y_marcador(self, imagen, esquinas):
        cv2.rectangle(imagen, (cn.ZONA_X1, cn.ZONA_Y1), (cn.ZONA_X2, cn.ZONA_Y2), (255, 255, 0), 3)
        if esquinas is not None:
            cv2.polylines(imagen, [esquinas.astype(np.int32)], True, (255, 0, 255), 4)

    def _dibujar_clasificador(self, imagen, naranjas, esquinas):
        self._dibujar_zona_y_marcador(imagen, esquinas)
        for i, n in enumerate(naranjas, start=1):
            arriba = int(n["y"] - n["largo_px"] / 2) - 12
            if not n["completa"]:
                cv2.ellipse(imagen, n["elipse"], (0, 0, 255), 3)
                texto, color = f"{i}: incompleta", (0, 0, 255)
            else:
                mm = cn.diametro_en_mm(n["largo_px"], n["acostada"])
                cv2.ellipse(imagen, n["elipse"], (0, 255, 0), 3)
                texto, color = f"{i}: {mm:.1f} mm {cn.clasificar(mm)}", (255, 255, 255)
            cv2.putText(imagen, texto, (n["x"] - 110, arriba), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 6)
            cv2.putText(imagen, texto, (n["x"] - 110, arriba), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    def _dibujar_cinta(self, imagen, seguidas, esquinas):
        self._dibujar_zona_y_marcador(imagen, esquinas)
        linea = ec.calcular_linea()
        if self.direccion in ("abajo", "arriba"):
            cv2.line(imagen, (cn.ZONA_X1, linea), (cn.ZONA_X2, linea), (0, 255, 255), 4)
        else:
            cv2.line(imagen, (linea, cn.ZONA_Y1), (linea, cn.ZONA_Y2), (0, 255, 255), 4)
        for fruta in seguidas:
            n = fruta["encontrada"]
            if n is None:
                continue
            if fruta["enviada"]:
                color, texto = (160, 160, 160), f"#{fruta['id']} {fruta['calibre']}"
            elif not n["completa"]:
                color, texto = (0, 0, 255), f"#{fruta['id']} incompleta"
            else:
                mm = cn.diametro_en_mm(n["largo_px"], n["acostada"])
                color, texto = (0, 255, 0), f"#{fruta['id']} {mm:.1f} mm"
            cv2.ellipse(imagen, n["elipse"], color, 3)
            arriba = int(n["y"] - n["largo_px"] / 2) - 12
            cv2.putText(imagen, texto, (n["x"] - 100, arriba), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 6)
            cv2.putText(imagen, texto, (n["x"] - 100, arriba), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # ---------------- Estado ----------------
    def estado(self):
        with self.candado:
            naranjas = list(self.naranjas)
            tiempos = list(self.tiempos)
            alto, ancho = (cn.ALTO, cn.ANCHO) if self.imagen is None else self.imagen.shape[:2]
        fps = (len(tiempos) - 1) / (tiempos[-1] - tiempos[0]) if len(tiempos) > 1 and tiempos[-1] > tiempos[0] else 0.0
        # Si no llega una imagen nueva hace más de 2 s, la cámara o el procesamiento se detuvo
        imagen_detenida = bool(tiempos) and time.time() - tiempos[-1] > 2.0
        if imagen_detenida:
            fps = 0.0
        lista = []
        for i, n in enumerate(naranjas, start=1):
            mm = round(cn.diametro_en_mm(n["largo_px"], n["acostada"]), 1)
            lista.append({"id": i, "mm": mm, "calibre": cn.clasificar(mm) if n["completa"] else "incompleta",
                          "completa": bool(n["completa"])})
        conteo = dict(self.conteo)
        conteo["total"] = sum(self.conteo.values())
        return {
            "calibrado": bool(cn.CALIBRADO),
            "escala": cn.ESCALA_FONDO,
            "autocalibrado": self.usar_autocalibracion and ac.ultima_escala is not None,
            "fps": round(fps, 1),
            "envio_activo": self.envio_activo,
            "direccion": self.direccion,
            "posicion_linea": self.posicion_linea,
            "zona": [cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2],
            "conteo": conteo,
            "ultimas": list(self.ultimas),
            "naranjas": lista,
            "grabando": self.quiere_grabar,
            "imagen_detenida": imagen_detenida,
            "ultimo_error_motor": self.ultimo_error_motor,
            "simulador_activo": self.simulador_activo,
            "url_estacion4": self.url_estacion4,
            "url_estacion5": self.url_estacion5,
            "errores_envio": self.errores_envio,
            "ultimo_error": self.ultimo_error,
            "mensaje_fuente": self.mensaje_fuente,
            "ancho_imagen": int(ancho),
            "alto_imagen": int(alto),
        }

    # ---------------- Acciones (botones de la página) ----------------
    def _reiniciar_seguimiento(self):
        """
        Al cambiar zona, línea o dirección, se olvidan las frutas que se estaban
        siguiendo, MENOS las que ya se enviaron: si no, al mover la línea más
        adelante una fruta ya enviada volvería a cruzarla y se enviaría dos veces.
        """
        with self.candado:
            self.seguidas = [f for f in self.seguidas if f["enviada"]]

    def calibrar(self):
        """Calibra con la naranja mediana: debe haber UNA sola naranja completa en la zona."""
        with self.candado:
            naranjas = list(self.naranjas)
        completas = [n for n in naranjas if n["completa"]]
        if len(completas) != 1:
            return False, (f"Se ven {len(completas)} naranjas completas en la zona. "
                           f"Deja SOLO la mediana ({cn.DIAMETRO_REFERENCIA_MM:.0f} mm), sin tocar el borde.")
        if completas[0]["circularidad"] < cn.CIRCULARIDAD_CALIBRACION:
            return False, "Parece que hay más de una fruta pegada. Separa la mediana de todo."
        # Misma cuenta que cn.calibrar, para saber de antemano si la escala es razonable
        H = cn.ALTURA_CAMARA_MM
        d_plano = cn.DIAMETRO_REFERENCIA_MM * H / (H - cn.ALTO_REFERENCIA_MM / 2)
        escala = d_plano / completas[0]["largo_px"]
        if not cn.ESCALA_MINIMA <= escala <= cn.ESCALA_MAXIMA:
            return False, "La escala resultante no es razonable. Revisa que solo esté la mediana."
        cn.calibrar(naranjas)
        aviso = " (el marcador, si se ve, puede volver a ajustarla)" if self.usar_autocalibracion else ""
        return True, f"Calibrado: {cn.ESCALA_FONDO:.4f} mm por píxel{aviso}"

    def fijar_zona(self, x1, y1, x2, y2):
        x1, x2 = sorted((int(x1), int(x2)))
        y1, y2 = sorted((int(y1), int(y2)))
        alto, ancho = self.estado()["alto_imagen"], self.estado()["ancho_imagen"]
        if x1 < 0 or y1 < 0 or x2 > ancho or y2 > alto:
            return False, "La zona sale de la imagen."
        if x2 - x1 < TAMANO_MINIMO_ZONA or y2 - y1 < TAMANO_MINIMO_ZONA:
            return False, f"La zona es muy chica (mínimo {TAMANO_MINIMO_ZONA} px por lado)."
        cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2 = x1, y1, x2, y2
        cn.guardar_configuracion()
        self._reiniciar_seguimiento()
        return True, f"Zona guardada: {x2 - x1} x {y2 - y1} px"

    def fijar_linea(self, fraccion):
        fraccion = float(fraccion)
        if not 0.0 < fraccion < 1.0:
            return False, "La línea debe quedar dentro de la zona."
        self.posicion_linea = round(fraccion, 3)
        ec.POSICION_LINEA = self.posicion_linea
        self._guardar_config_cinta()
        self._reiniciar_seguimiento()
        return True, f"Línea de decisión en {self.posicion_linea:.2f} de la zona"

    def fijar_direccion(self, direccion):
        if direccion not in DIRECCIONES:
            return False, "Dirección no válida."
        self.direccion = direccion
        ec.DIRECCION = direccion
        self._guardar_config_cinta()
        self._reiniciar_seguimiento()
        return True, f"Las naranjas avanzan hacia {direccion}"

    def fijar_urls(self, url4, url5):
        for url in (url4, url5):
            if not str(url).startswith(("http://", "https://")):
                return False, "Las direcciones deben empezar con http://"
        self.url_estacion4, self.url_estacion5 = str(url4), str(url5)
        self._guardar_config_cinta()
        return True, "Direcciones de las estaciones guardadas"

    def fijar_envio(self, activo):
        self.envio_activo = bool(activo)

    def fijar_simulador(self, activo):
        self.simulador_activo = bool(activo)
        self._guardar_config_cinta()

    def reiniciar(self):
        with self.candado:
            self.conteo = {"chico": 0, "mediano": 0, "grande": 0, "revision": 0}
            self.ultimas = []
            self.seguidas = []
            self.errores_envio = 0
            self.ultimo_error = ""
            self.ultimo_error_motor = ""

    def guardar_foto(self):
        with self.candado:
            imagen = None if self.imagen is None else self.imagen.copy()
        if imagen is None:
            return ""
        carpeta = self._ruta(cn.CARPETA_FOTOS)
        os.makedirs(carpeta, exist_ok=True)
        numero = len([f for f in os.listdir(carpeta) if f.endswith(".jpg")])
        ruta = os.path.join(carpeta, f"naranja_{numero:04d}.jpg")
        while os.path.exists(ruta):
            numero += 1
            ruta = os.path.join(carpeta, f"naranja_{numero:04d}.jpg")
        cv2.imwrite(ruta, imagen)
        return ruta

    def alternar_grabacion(self):
        """
        Pide empezar o terminar de grabar. Devuelve True si quedará grabando.
        El archivo lo abre y lo cierra el hilo de la cámara en la imagen siguiente:
        cerrarlo desde la página mientras la cámara escribe puede cerrar la app.
        """
        self.quiere_grabar = not self.quiere_grabar
        return self.quiere_grabar

    def _actualizar_grabacion(self, frame):
        """(Hilo de la cámara) Abre o cierra el archivo de video según lo pedido."""
        if self.quiere_grabar and self.grabador is None:
            with self.candado:
                tiempos = list(self.tiempos)
            fps = (len(tiempos) - 1) / (tiempos[-1] - tiempos[0]) if len(tiempos) > 1 and tiempos[-1] > tiempos[0] else 10.0
            carpeta = self._ruta(ec.CARPETA_VIDEOS)
            os.makedirs(carpeta, exist_ok=True)
            ruta = os.path.join(carpeta, datetime.now().strftime("cinta_%Y%m%d_%H%M%S.mp4"))
            alto, ancho = frame.shape[:2]
            grabador = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"mp4v"), max(1.0, fps), (ancho, alto))
            if grabador.isOpened():
                self.grabador = grabador
            else:
                self.quiere_grabar = False
                self.ultimo_error_motor = f"No se pudo crear el video {ruta}"
        elif not self.quiere_grabar and self.grabador is not None:
            self.grabador.release()
            self.grabador = None

    def cerrar(self):
        """Al salir de la app: cierra el video si se estaba grabando (para que se pueda abrir)."""
        if self.grabador is not None:
            self.grabador.release()
            self.grabador = None
