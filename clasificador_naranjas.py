"""
Fase 0 - Clasificador de naranjas por diámetro (sin entrenamiento)
------------------------------------------------------------------
Detecta naranjas por color dentro de la zona de trabajo (el marco de PVC),
separa las que están tocándose, mide su diámetro y las clasifica en
chico / mediano / grande.

Cámara: webcam externa LINK ON (USB), fija sobre el marco a la altura oficial.

Requisitos:  pip install opencv-python numpy

Teclas:
  c  -> calibrar (pon UNA naranja medida con pie de metro dentro del marco)
  s  -> guardar la imagen actual (sirve para armar el dataset de la fase 2)
  q  -> salir
"""

import os
import cv2
import numpy as np

# ---------------- Configuración ----------------
# Índice de la webcam LINK ON (en este Mac es la 0).
CAMARA = 0
ANCHO = 1920
ALTO = 1080

# Zona de trabajo: rectángulo dentro del marco de PVC (en píxeles, para 1920x1080).
# Todo lo que quede fuera (tubos, piso, zapatos) se ignora.
# Si mueves la cámara, ajusta estos 4 valores mirando el rectángulo celeste.
ZONA_X1 = 600
ZONA_Y1 = 210
ZONA_X2 = 1425
ZONA_Y2 = 945

DIAMETRO_REFERENCIA_MM = 60.0    # diámetro real de la naranja de calibración
MM_POR_PIXEL = None              # se calcula al presionar 'c' (luego copia el valor aquí)

# Límites de cada categoría EN PÍXELES (altura oficial de la cámara).
# Diámetros medidos en la prueba con 9 frutas:
#   153 | 173 174 174 179 | 186 190 194 196
# Los límites están en los "saltos" entre grupos.
LIMITE_CHICO_PX = 165
LIMITE_GRANDE_PX = 183

# Límites de cada categoría EN MM (se usan después de calibrar con 'c').
# EJEMPLO: reemplazar por la norma de calibres que usen.
LIMITE_CHICO_MM = 55.0
LIMITE_GRANDE_MM = 65.0

AREA_MINIMA = 5000               # en píxeles, para ignorar manchas pequeñas
CIRCULARIDAD_MINIMA = 0.65       # 1.0 = círculo perfecto; las manchas irregulares dan menos

# Rango del color naranja en HSV.
# H = tono, S = saturación (qué tan "vivo" es el color), V = brillo.
# El tono parte en 0 para incluir las frutas más rojizas.
# El cartón tiene casi el mismo tono, pero es poco saturado (por eso S mínimo = 150).
NARANJA_BAJO = np.array([0, 150, 100])
NARANJA_ALTO = np.array([25, 255, 255])
# El rojo también aparece al final de la escala de tono (170-180).
ROJO_BAJO = np.array([170, 150, 100])
ROJO_ALTO = np.array([180, 255, 255])

CARPETA_FOTOS = "fotos"


def listar_camaras(maximo=5):
    """Prueba los índices 0..maximo-1 y muestra cuáles entregan imagen."""
    print("Buscando cámaras...")
    for i in range(maximo):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                alto, ancho = frame.shape[:2]
                print(f"  Cámara {i}: OK ({ancho}x{alto})")
        cap.release()


def clasificar(diametro, limite_chico, limite_grande):
    if diametro < limite_chico:
        return "chico"
    elif diametro < limite_grande:
        return "mediano"
    else:
        return "grande"


def crear_mascara(frame):
    """Imagen en blanco y negro: blanco = color naranja dentro de la zona."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mascara = cv2.inRange(hsv, NARANJA_BAJO, NARANJA_ALTO)
    mascara_roja = cv2.inRange(hsv, ROJO_BAJO, ROJO_ALTO)
    mascara = cv2.bitwise_or(mascara, mascara_roja)

    # Borrar todo lo que esté fuera de la zona de trabajo
    zona = np.zeros_like(mascara)
    zona[ZONA_Y1:ZONA_Y2, ZONA_X1:ZONA_X2] = 255
    mascara = cv2.bitwise_and(mascara, zona)

    # Limpiar ruido y rellenar huecos (brillos de la cáscara)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))

    # Rellenar por completo cada mancha (por ejemplo, el tallo verde)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mascara = np.zeros_like(mascara)
    cv2.drawContours(mascara, contornos, -1, 255, -1)
    return mascara


def separar_frutas(frame, mascara):
    """
    Separa frutas que se tocan usando "watershed" (cuencas):
      1. La transformada de distancia indica, para cada píxel blanco,
         qué tan lejos está del borde. El centro de cada fruta es el punto
         más lejano, aunque dos frutas estén pegadas.
      2. Esos centros se usan como "semillas" y watershed hace crecer
         cada semilla hasta encontrarse con la de la fruta vecina.
    Devuelve una imagen de etiquetas (cada fruta tiene un número) y
    cuántas frutas encontró.
    """
    distancia = cv2.distanceTransform(mascara, cv2.DIST_L2, 5)
    if distancia.max() == 0:
        return None, 0

    # Centros: zonas que están a más de la mitad de la distancia máxima del borde
    _, centros = cv2.threshold(distancia, 0.5 * distancia.max(), 255, cv2.THRESH_BINARY)
    centros = centros.astype(np.uint8)
    cantidad, etiquetas = cv2.connectedComponents(centros)

    # Zona dudosa = fruta que todavía no se sabe a qué semilla pertenece
    fondo_seguro = cv2.dilate(mascara, np.ones((3, 3), np.uint8), iterations=3)
    dudosa = cv2.subtract(fondo_seguro, centros)

    etiquetas = etiquetas + 1        # el fondo pasa a ser 1 (watershed usa 0 = dudoso)
    etiquetas[dudosa == 255] = 0
    etiquetas = cv2.watershed(frame, etiquetas)
    return etiquetas, cantidad - 1   # se resta el fondo


def buscar_naranjas(frame):
    """Devuelve la máscara y una lista de (x, y, radio_px) por cada naranja."""
    mascara = crear_mascara(frame)
    etiquetas, cantidad = separar_frutas(frame, mascara)

    naranjas = []
    if etiquetas is None:
        return mascara, naranjas

    # Las frutas tienen etiquetas 2, 3, 4, ... (1 es el fondo)
    for numero in range(2, cantidad + 2):
        region = np.uint8(etiquetas == numero) * 255
        region = cv2.bitwise_and(region, mascara)

        contornos, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contornos) == 0:
            continue
        c = max(contornos, key=cv2.contourArea)

        area = cv2.contourArea(c)
        if area < AREA_MINIMA:
            continue
        (x, y), radio = cv2.minEnclosingCircle(c)

        # Circularidad: qué parte del círculo que la rodea está "llena".
        circularidad = area / (np.pi * radio ** 2)
        if circularidad < CIRCULARIDAD_MINIMA:
            continue

        naranjas.append((int(x), int(y), radio))
    return mascara, naranjas


# ---------------- Programa principal ----------------
listar_camaras()

cap = cv2.VideoCapture(CAMARA)
if not cap.isOpened():
    raise SystemExit(f"No se pudo abrir la cámara {CAMARA}. Cambia CAMARA por uno de los índices de arriba.")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
# Si la cámara tiene autoenfoque, apagarlo ayuda a que la escala no cambie.
# (Algunas cámaras o sistemas ignoran esta línea; no pasa nada si es así.)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

# Dos ventanas lado a lado, a la mitad del tamaño para que quepan en pantalla
cv2.namedWindow("Clasificador", cv2.WINDOW_NORMAL)
cv2.namedWindow("Mascara", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Clasificador", ANCHO // 2, ALTO // 2)
cv2.resizeWindow("Mascara", ANCHO // 2, ALTO // 2)
cv2.moveWindow("Clasificador", 0, 0)
cv2.moveWindow("Mascara", ANCHO // 2 + 10, 0)

os.makedirs(CARPETA_FOTOS, exist_ok=True)
contador_fotos = 0

while True:
    ok, frame = cap.read()
    if not ok:
        print("No se pudo leer la cámara")
        break

    original = frame.copy()
    mascara, naranjas = buscar_naranjas(frame)

    # Rectángulo de la zona de trabajo
    cv2.rectangle(frame, (ZONA_X1, ZONA_Y1), (ZONA_X2, ZONA_Y2), (255, 255, 0), 2)

    conteo = {"chico": 0, "mediano": 0, "grande": 0}
    for (x, y, radio) in naranjas:
        diametro_px = 2 * radio

        if MM_POR_PIXEL is None:
            categoria = clasificar(diametro_px, LIMITE_CHICO_PX, LIMITE_GRANDE_PX)
            texto = f"{diametro_px:.0f} px - {categoria}"
        else:
            diametro_mm = diametro_px * MM_POR_PIXEL
            categoria = clasificar(diametro_mm, LIMITE_CHICO_MM, LIMITE_GRANDE_MM)
            texto = f"{diametro_mm:.1f} mm - {categoria}"
        conteo[categoria] += 1

        cv2.circle(frame, (x, y), int(radio), (0, 255, 0), 2)
        cv2.putText(frame, texto, (x - 80, y - int(radio) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Resumen arriba a la izquierda
    resumen = f"Chicas: {conteo['chico']}  Medianas: {conteo['mediano']}  Grandes: {conteo['grande']}"
    cv2.putText(frame, resumen, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

    cv2.imshow("Clasificador", frame)
    cv2.imshow("Mascara", mascara)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla == ord('q'):
        break
    elif tecla == ord('c'):
        if len(naranjas) == 1:
            diametro_px = 2 * naranjas[0][2]
            MM_POR_PIXEL = DIAMETRO_REFERENCIA_MM / diametro_px
            print(f"Calibrado: {MM_POR_PIXEL:.4f} mm por píxel")
            print(f"Copia esto en el archivo:  MM_POR_PIXEL = {MM_POR_PIXEL:.4f}")
        else:
            print("Para calibrar debe haber exactamente UNA naranja dentro del marco")
    elif tecla == ord('s'):
        ruta = os.path.join(CARPETA_FOTOS, f"naranja_{contador_fotos:04d}.jpg")
        cv2.imwrite(ruta, original)
        contador_fotos += 1
        print("Guardada:", ruta)

cap.release()
cv2.destroyAllWindows()
cv2.waitKey(1)   # en macOS/Spyder ayuda a que las ventanas se cierren de verdad
