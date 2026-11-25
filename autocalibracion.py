"""
Autocalibración con un marcador impreso (ArUco)
-----------------------------------------------
En vez de calibrar con la naranja mediana (tecla c), se pega al costado de
la cinta un cuadrado impreso de tamaño conocido (un marcador "ArUco", parecido
a un código QR). El programa lo encuentra solo en la imagen, mide cuántos
píxeles mide su lado y calcula la escala:

    escala (mm por píxel) = tamaño real del marcador (mm) / lado en píxeles

Así el sistema se calibra solo cada vez que parte, y si alguien mueve la
cámara, se vuelve a calibrar sin tocar ninguna fruta.

Dónde poner el marcador:
  - Dentro de la imagen, pero FUERA del camino de las naranjas.
  - A la MISMA ALTURA que la superficie de la cinta (no sobre el marco):
    1 cm más arriba ya cambia la escala en ~3 %.
  - Plano, sin arrugas y sin reflejos.

Uso:
    python3 autocalibracion.py           -> crea marcador_calibracion.pdf para imprimir
    python3 autocalibracion.py probar    -> abre la cámara y muestra la escala que mide

Al imprimir: tamaño real / 100 % (NO "ajustar a la página"). Después medir
con regla el lado del cuadrado negro y anotarlo en TAMANO_MARCADOR_MM.
"""

import sys

import cv2
import numpy as np

import clasificador_naranjas as cn

# ---------------- Configuración ----------------
TAMANO_MARCADOR_MM = 60.0     # lado del cuadrado negro, MEDIDO CON REGLA después de imprimir
ALTURA_MARCADOR_MM = 0.0      # cuánto más arriba que la cinta quedó pegado (ideal: 0)
ID_MARCADOR = 0
DICCIONARIO = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
parametros = cv2.aruco.DetectorParameters()
parametros.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX   # esquinas más precisas
detector = cv2.aruco.ArucoDetector(DICCIONARIO, parametros)

IMAGENES_PARA_CALIBRAR = 15   # se promedia la medida de varias imágenes
CAMBIO_MINIMO = 0.01          # recalibrar solo si la escala cambia más de 1 %

lados_recientes = []          # medidas del lado del marcador (px) en las últimas imágenes
contador_imagenes = 0
ultima_escala = None          # última escala medida con el marcador (para mostrarla en pantalla)


# ---------------- Medir el marcador ----------------
def medir_marcador(frame):
    """
    Busca el marcador en la imagen. Devuelve (lado en píxeles, esquinas)
    o (None, None) si no aparece.
    """
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    esquinas, ids, _ = detector.detectMarkers(gris)
    if ids is None:
        return None, None
    for e, i in zip(esquinas, ids.flatten()):
        if i == ID_MARCADOR:
            p = e.reshape(4, 2)
            # promedio de los 4 lados del cuadrado
            lados = [np.linalg.norm(p[k] - p[(k + 1) % 4]) for k in range(4)]
            return float(np.mean(lados)), p
    return None, None


def escala_desde_lado(lado_px):
    """
    mm por píxel a la altura de la cinta. Si el marcador quedó un poco más
    arriba que la cinta, se ve más grande; se corrige igual que la altura
    de la fruta (el tamaño aparente es inversamente proporcional a la distancia).
    """
    escala_marcador = TAMANO_MARCADOR_MM / lado_px
    H = cn.ALTURA_CAMARA_MM
    return escala_marcador * H / (H - ALTURA_MARCADOR_MM)


def aplicar_escala(escala):
    """Usa la escala nueva en el clasificador y la guarda en configuracion.json."""
    if not (cn.ESCALA_MINIMA <= escala <= cn.ESCALA_MAXIMA):
        print(f"Autocalibración descartada: escala {escala:.4f} mm/px fuera de rango")
        return False
    cn.ESCALA_FONDO = escala
    cn.CALIBRADO = True
    cn.guardar_configuracion()
    print(f"Autocalibrado con el marcador: {escala:.4f} mm por píxel")
    return True


def revisar(frame):
    """
    Llamar en cada imagen del programa principal. Al partir mide el marcador
    en las primeras imágenes y calibra; después lo revisa de vez en cuando
    (cada 30 imágenes) y recalibra solo si la cámara se movió.
    Devuelve las esquinas del marcador (para dibujarlo) o None.
    """
    global contador_imagenes, ultima_escala
    contador_imagenes += 1
    calibrando = contador_imagenes <= IMAGENES_PARA_CALIBRAR * 2
    if not calibrando and contador_imagenes % 30 != 0:
        return None

    lado, esquinas = medir_marcador(frame)
    if lado is None:
        return None
    lados_recientes.append(lado)
    if len(lados_recientes) > IMAGENES_PARA_CALIBRAR:
        lados_recientes.pop(0)

    if len(lados_recientes) == IMAGENES_PARA_CALIBRAR:
        escala = escala_desde_lado(float(np.median(lados_recientes)))
        ultima_escala = escala
        if abs(escala - cn.ESCALA_FONDO) / cn.ESCALA_FONDO > CAMBIO_MINIMO or not cn.CALIBRADO:
            aplicar_escala(escala)
    return esquinas


# ---------------- Crear el marcador para imprimir ----------------
def crear_pdf(nombre="marcador_calibracion.pdf"):
    """
    Hoja A4 a 10 píxeles por mm (254 dpi): el marcador de 60 mm mide
    exactamente 600 px. Incluye una regla de 100 mm para comprobar que la
    impresora no cambió el tamaño.
    """
    from PIL import Image
    px_mm = 10
    hoja = np.full((297 * px_mm, 210 * px_mm), 255, np.uint8)

    lado = int(60 * px_mm)
    marcador = cv2.aruco.generateImageMarker(DICCIONARIO, ID_MARCADOR, lado)
    x0, y0 = (hoja.shape[1] - lado) // 2, 60 * px_mm
    hoja[y0:y0 + lado, x0:x0 + lado] = marcador

    # Regla de 100 mm con marcas cada 10 mm
    yr = y0 + lado + 40 * px_mm
    xr = (hoja.shape[1] - 100 * px_mm) // 2
    cv2.line(hoja, (xr, yr), (xr + 100 * px_mm, yr), 0, 4)
    for k in range(11):
        alto = 40 if k % 5 == 0 else 20
        cv2.line(hoja, (xr + k * 10 * px_mm, yr - alto), (xr + k * 10 * px_mm, yr), 0, 4)

    textos = ["Marcador de calibracion - Estacion 3 (PackIA Coquimbo)",
              "Imprimir a tamano real (100 %), NO 'ajustar a la pagina'.",
              "El cuadrado negro debe medir 60 mm y la regla 100 mm.",
              "Si no miden eso, anotar la medida real en TAMANO_MARCADOR_MM.",
              "Pegar al costado de la cinta, a la misma altura que la cinta."]
    for k, t in enumerate(textos):
        cv2.putText(hoja, t, (15 * px_mm, 22 * px_mm + k * 70), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 0, 3)
    cv2.putText(hoja, "100 mm", (xr + 40 * px_mm, yr + 90), cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 4)

    Image.fromarray(hoja).save(nombre, resolution=254)
    print("Creado", nombre, "- imprimir a tamaño real (100 %)")


# ---------------- Probar con la cámara ----------------
def probar():
    """Muestra el marcador detectado y la escala que mide, comparada con la guardada."""
    cn.cargar_configuracion()
    guardada = cn.ESCALA_FONDO
    cap = cv2.VideoCapture(cn.CAMARA)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cn.ANCHO)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cn.ALTO)
    cv2.namedWindow("Marcador", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Marcador", cn.ANCHO // 2, cn.ALTO // 2)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        lado, esquinas = medir_marcador(frame)
        if lado is None:
            texto, color = "Marcador NO encontrado", (0, 0, 255)
        else:
            escala = escala_desde_lado(lado)
            dif = 100 * (escala - guardada) / guardada
            texto = f"Lado {lado:.1f} px -> {escala:.4f} mm/px  (guardada {guardada:.4f}, {dif:+.1f} %)"
            color = (0, 255, 0)
            cv2.polylines(frame, [esquinas.astype(np.int32)], True, color, 4)
        cv2.putText(frame, texto, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
        cv2.imshow("Marcador", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "probar":
        probar()
    else:
        crear_pdf()
