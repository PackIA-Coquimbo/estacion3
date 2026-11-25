"""
Estación 3 - Modo cinta transportadora
--------------------------------------
Las naranjas pasan EN FILA por la cinta. El programa sigue a cada naranja
mientras cruza la imagen, la mide varias veces y, cuando su centro cruza la
LÍNEA DE DECISIÓN, la clasifica (chico / mediano / grande) y avisa de
inmediato por HTTP a:
  - Estación 4: mueve el servo para separar la fruta según su calibre.
  - Estación 5: dashboard con el total y cuántas hay de cada calibre.

Cada fruta se cuenta y se envía UNA sola vez.

Reutiliza la detección, la medición y la calibración de clasificador_naranjas.py
(calibrar y elegir la zona se sigue haciendo con ese programa, teclas c y z).

Uso (en la carpeta Clasificador, con el venv activado):
    python3 estacion3_cinta.py

Para probar sin las otras estaciones, en OTRA terminal:
    python3 simulador_estaciones.py

Teclas:  q = salir    r = reiniciar contadores    g = empezar / terminar de grabar video
"""

import csv
import os
import sys
import threading
import time
import warnings
from datetime import datetime

import cv2
import numpy as np
warnings.filterwarnings("ignore", message="urllib3 v2")   # aviso inofensivo del Python del Mac
import requests

import clasificador_naranjas as cn   # detección, medición y calibración
import autocalibracion as ac         # calibración automática con el marcador impreso

# ---------------- Configuración ----------------
# Cámara (número) o un video grabado de la cinta (ruta al archivo .mp4)
FUENTE = 0

# Dirección en que avanza la cinta en la imagen: "derecha" (izquierda -> derecha)
# o "izquierda" (derecha -> izquierda)
DIRECCION = "derecha"

# Posición de la línea de decisión, como fracción del ancho de la zona
# (0.5 = al medio). La fruta se mide mientras se acerca y se decide al cruzarla.
POSICION_LINEA = 0.6

# Direcciones de las otras estaciones (cambiarlas por las IP reales del router)
URL_ESTACION4 = "http://127.0.0.1:5004/fruta"
URL_ESTACION5 = "http://127.0.0.1:5005/fruta"
TIEMPO_ESPERA_HTTP = 1.0      # segundos máximos esperando respuesta

# Seguimiento
DISTANCIA_MAXIMA = 150        # px: una fruta no salta más que esto entre dos imágenes
IMAGENES_PERDIDA = 10         # si no se ve en tantas imágenes seguidas, se olvida
MEDIDAS_MINIMAS = 3           # medidas necesarias para decidir con confianza

ARCHIVO_REGISTRO = "registro_frutas.csv"

# Calibrarse solo con el marcador impreso (ver autocalibracion.py).
# Si no se ve el marcador, se usa la calibración guardada en configuracion.json.
USAR_AUTOCALIBRACION = True

# Videos grabados con la tecla g
CARPETA_VIDEOS = "videos"


# ---------------- Envío por HTTP ----------------
def enviar(url, datos):
    """Envía los datos (JSON) a una estación. Si falla, solo avisa por la terminal."""
    try:
        r = requests.post(url, json=datos, timeout=TIEMPO_ESPERA_HTTP)
        if r.status_code != 200:
            print(f"  ! {url} respondió {r.status_code}")
    except requests.exceptions.RequestException:
        print(f"  ! No se pudo enviar a {url} (¿está encendida esa estación?)")


def avisar_estaciones(datos):
    """
    Envía a las estaciones 4 y 5 al mismo tiempo, en segundo plano, para que
    la cámara no se detenga esperando la respuesta de la red.
    """
    for url in [URL_ESTACION4, URL_ESTACION5]:
        threading.Thread(target=enviar, args=(url, datos), daemon=True).start()


def guardar_registro(datos):
    """Agrega una fila al archivo CSV con cada fruta clasificada."""
    nuevo = not os.path.exists(ARCHIVO_REGISTRO)
    with open(ARCHIVO_REGISTRO, "a", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(datos.keys()))
        if nuevo:
            escritor.writeheader()
        escritor.writerow(datos)


# ---------------- Seguimiento de frutas ----------------
def cruzo_la_linea(x_anterior, x_actual, linea):
    """True si el centro de la fruta acaba de pasar la línea de decisión."""
    if DIRECCION == "derecha":
        return x_anterior < linea <= x_actual
    return x_anterior > linea >= x_actual


def antes_de_la_linea(x, linea):
    return x < linea if DIRECCION == "derecha" else x > linea


def actualizar_seguimiento(seguidas, naranjas, siguiente_id):
    """
    Junta cada naranja detectada en esta imagen con la fruta seguida más
    cercana (la misma fruta, un poco más adelante en la cinta).
    Las naranjas que no se parecen a ninguna son frutas nuevas.
    Devuelve el siguiente número de fruta disponible.
    """
    usadas = set()
    for fruta in seguidas:
        fruta["encontrada"] = None
        mejor, mejor_d = None, DISTANCIA_MAXIMA
        for i, n in enumerate(naranjas):
            d = np.hypot(n["x"] - fruta["x"], n["y"] - fruta["y"])
            if i not in usadas and d < mejor_d:
                mejor, mejor_d = i, d
        if mejor is None:
            fruta["perdida"] += 1
        else:
            usadas.add(mejor)
            fruta["encontrada"] = naranjas[mejor]
            fruta["perdida"] = 0

    # Frutas nuevas (las que acaban de entrar a la zona)
    for i, n in enumerate(naranjas):
        if i not in usadas:
            seguidas.append({"id": siguiente_id, "x": n["x"], "y": n["y"], "medidas": [],
                             "enviada": False, "perdida": 0, "encontrada": n, "nueva": True})
            siguiente_id += 1

    # Olvidar las que ya no se ven
    seguidas[:] = [f for f in seguidas if f["perdida"] <= IMAGENES_PERDIDA]
    return siguiente_id


def decidir(fruta):
    """
    Calcula el calibre final de una fruta con todas las medidas que se
    tomaron mientras se acercaba a la línea. Se usa la mediana: si una
    medida salió mal (un reflejo, un salto de la cinta), no cambia el resultado.
    """
    if len(fruta["medidas"]) == 0:
        # Nunca se vio completa (por ejemplo, venía pegada a otra fruta)
        return "revision", None
    diametro = float(np.median(fruta["medidas"]))
    return cn.clasificar(diametro), diametro


# ---------------- Programa principal ----------------
if __name__ == "__main__":
    # Opcional: python3 estacion3_cinta.py video_cinta.mp4  (probar con un video grabado)
    if len(sys.argv) > 1:
        FUENTE = sys.argv[1]
    cn.cargar_configuracion()

    cap = cv2.VideoCapture(FUENTE)
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir la fuente de video {FUENTE}")
    if isinstance(FUENTE, int):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cn.ANCHO)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cn.ALTO)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

    cv2.namedWindow("Estacion 3 - Cinta", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Estacion 3 - Cinta", cn.ANCHO // 2, cn.ALTO // 2)

    grabador = None        # cv2.VideoWriter mientras se graba con la tecla g
    seguidas = []          # frutas que se están siguiendo en la cinta
    siguiente_id = 1
    conteo = {"chico": 0, "mediano": 0, "grande": 0, "revision": 0}
    print(f"Detector: {'YOLO' if cn.USAR_YOLO else 'color'} | cinta hacia la {DIRECCION}")
    print(f"Enviando a {URL_ESTACION4} y {URL_ESTACION5}")

    inicio = time.time()
    imagenes_procesadas = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Fin del video o no se pudo leer la cámara")
            break
        imagenes_procesadas += 1

        if grabador is not None:
            grabador.write(frame)            # se graba la imagen limpia, sin dibujos

        esquinas_marcador = ac.revisar(frame) if USAR_AUTOCALIBRACION else None

        _, naranjas = cn.buscar_naranjas(frame)
        linea = int(cn.ZONA_X1 + POSICION_LINEA * (cn.ZONA_X2 - cn.ZONA_X1))
        siguiente_id = actualizar_seguimiento(seguidas, naranjas, siguiente_id)

        for fruta in seguidas:
            n = fruta["encontrada"]
            if n is None:
                continue
            x_anterior = fruta["x"]

            # Medir mientras se acerca a la línea (solo si se ve completa)
            if not fruta["enviada"] and n["completa"] and antes_de_la_linea(n["x"], linea + 1):
                fruta["medidas"].append(cn.diametro_en_mm(n["largo_px"], n["acostada"]))

            # ¿Cruzó la línea? -> clasificar y avisar a las estaciones 4 y 5
            if not fruta["enviada"] and not fruta["nueva"] and cruzo_la_linea(x_anterior, n["x"], linea):
                calibre, diametro = decidir(fruta)
                datos = {
                    "estacion": 3,
                    "id": fruta["id"],
                    "calibre": calibre,
                    "diametro_mm": None if diametro is None else round(diametro, 1),
                    "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                avisar_estaciones(datos)
                guardar_registro(datos)
                conteo[calibre] += 1
                fruta["enviada"] = True
                fruta["calibre"] = calibre
                texto_mm = "sin medida" if diametro is None else f"{diametro:.1f} mm"
                print(f"Fruta {fruta['id']}: {texto_mm} -> {calibre}  "
                      f"({len(fruta['medidas'])} medidas)")

            fruta["x"], fruta["y"] = n["x"], n["y"]
            fruta["nueva"] = False

        # ---------- Dibujar ----------
        cv2.rectangle(frame, (cn.ZONA_X1, cn.ZONA_Y1), (cn.ZONA_X2, cn.ZONA_Y2), (255, 255, 0), 2)
        cv2.line(frame, (linea, cn.ZONA_Y1), (linea, cn.ZONA_Y2), (0, 255, 255), 3)
        cv2.putText(frame, "linea de decision", (linea + 8, cn.ZONA_Y1 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        for fruta in seguidas:
            n = fruta["encontrada"]
            if n is None:
                continue
            if fruta["enviada"]:
                color, texto = (160, 160, 160), f"#{fruta['id']} {fruta['calibre']} (enviada)"
            elif not n["completa"]:
                color, texto = (0, 0, 255), f"#{fruta['id']} incompleta"
            else:
                mm = cn.diametro_en_mm(n["largo_px"], n["acostada"])
                color, texto = (0, 255, 0), f"#{fruta['id']} {mm:.1f} mm"
            cv2.ellipse(frame, n["elipse"], color, 2)
            arriba = int(n["y"] - n["largo_px"] / 2) - 10
            cv2.putText(frame, texto, (n["x"] - 90, arriba), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        total = conteo["chico"] + conteo["mediano"] + conteo["grande"] + conteo["revision"]
        resumen = (f"Total: {total}   Chicas: {conteo['chico']}   Medianas: {conteo['mediano']}   "
                   f"Grandes: {conteo['grande']}   Revision: {conteo['revision']}")
        cv2.putText(frame, resumen, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

        # Estado de la calibración
        if esquinas_marcador is not None:
            cv2.polylines(frame, [esquinas_marcador.astype(np.int32)], True, (255, 0, 255), 3)
        if ac.ultima_escala is not None:
            texto_cal, color_cal = f"Autocalibrado con marcador: {cn.ESCALA_FONDO:.4f} mm/px", (0, 255, 0)
        elif cn.CALIBRADO:
            texto_cal, color_cal = f"Calibracion guardada: {cn.ESCALA_FONDO:.4f} mm/px (sin marcador)", (0, 200, 255)
        else:
            texto_cal, color_cal = "SIN CALIBRAR: falta el marcador o calibrar con c", (0, 0, 255)
        cv2.putText(frame, texto_cal, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_cal, 2)
        if grabador is not None:
            cv2.circle(frame, (cn.ANCHO - 60, 50), 18, (0, 0, 255), -1)
            cv2.putText(frame, "REC", (cn.ANCHO - 140, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        cv2.imshow("Estacion 3 - Cinta", frame)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('q'):
            break
        elif tecla == ord('r'):
            conteo = {"chico": 0, "mediano": 0, "grande": 0, "revision": 0}
            print("Contadores reiniciados")
        elif tecla == ord('g'):
            if grabador is None:
                os.makedirs(CARPETA_VIDEOS, exist_ok=True)
                ruta = os.path.join(CARPETA_VIDEOS, datetime.now().strftime("cinta_%Y%m%d_%H%M%S.mp4"))
                # Se graba a la velocidad real del programa (imágenes procesadas por segundo),
                # así el video se ve a la velocidad real de la cinta.
                fps = max(1.0, imagenes_procesadas / (time.time() - inicio))
                alto, ancho = frame.shape[:2]
                grabador = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))
                print("Grabando video en", ruta, "(g para terminar)")
            else:
                grabador.release()
                grabador = None
                print("Video guardado")

    if grabador is not None:
        grabador.release()
    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)
