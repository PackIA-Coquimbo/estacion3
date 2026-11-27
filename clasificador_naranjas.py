"""
Fase 0 - Clasificador de naranjas por diámetro (sin entrenamiento)
------------------------------------------------------------------
Detecta naranjas por color dentro de la zona de trabajo (fondo negro),
separa las que están tocándose, mide su largo en mm y las clasifica en
chico / mediano / grande.

Cámara: webcam externa LINK ON (USB), fija a ~35 cm sobre el fondo negro.

Requisitos:  pip install opencv-python numpy

Teclas (con la ventana "Clasificador" seleccionada):
  c  -> calibrar: deja SOLO la naranja mediana (62 mm) en la zona y presiona c
  z  -> cambiar la zona de trabajo: arrastra un rectángulo con el mouse y presiona Enter
  m  -> imprimir en la Terminal las medidas actuales (para la tabla de validación)
  s  -> guardar la imagen actual (sirve para armar el dataset de la fase 2)
  q  -> salir

La calibración y la zona se guardan en "configuracion.json", así que
no hay que repetirlas cada vez que se abre el programa.
"""

import os
import json
import cv2
import numpy as np

# Trabajar en la carpeta donde está este archivo (así configuracion.json y la
# carpeta fotos quedan junto al código, aunque se ejecute desde Spyder).
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    pass

# ---------------- Configuración ----------------
# Índice de la webcam LINK ON (en este Mac es la 0).
CAMARA = 0
ANCHO = 1920
ALTO = 1080

# Zona de trabajo inicial (en píxeles). Se puede cambiar en vivo con la tecla 'z'.
# Lo ideal es que cubra SOLO la superficie negra (sin madera ni tubos).
ZONA_X1 = 555
ZONA_Y1 = 195
ZONA_X2 = 1410
ZONA_Y2 = 1045

# Distancia de la cámara al fondo negro (medida con huincha: 350 mm +- 12 mm).
ALTURA_CAMARA_MM = 350.0

# Medidas reales de las frutas de referencia (desde arriba):
#   chica   = 55 mm de largo, 30 mm de alto
#   mediana = 62 mm de largo, 40 mm de alto
#   grande  = 68 mm de largo, 50 mm de alto
# Para calibrar con 'c' se usa la mediana.
DIAMETRO_REFERENCIA_MM = 62.0
ALTO_REFERENCIA_MM = 40.0

# Alto / largo promedio de las frutas: (30/55 + 40/62 + 50/68) / 3 = 0,65
RELACION_ALTO_DIAMETRO = 0.65

# Si la fruta se ve muy ovalada (ancho / largo menor a esto), está acostada:
# su parte más ancha queda a la mitad de su LARGO (no de su alto), más cerca
# de la cámara, y se corrige distinto.
RELACION_ACOSTADA = 0.80

# Escala sobre el fondo negro (mm por píxel). Es una ESTIMACIÓN inicial;
# se reemplaza al calibrar con 'c' y queda guardada en configuracion.json.
ESCALA_FONDO = 0.29
CALIBRADO = False

# Límites de cada categoría en mm (puntos medios entre las medidas reales):
#   (55 + 62) / 2 = 58,5      (62 + 68) / 2 = 65
LIMITE_CHICO_MM = 58.5
LIMITE_GRANDE_MM = 65.0

AREA_MINIMA = 5000               # en píxeles, para ignorar manchas pequeñas

# Circularidad = área de la fruta / área del círculo que la rodea (1.0 = círculo perfecto).
# Se calcula con el contorno "envolvente" (convex hull), así los brillos o
# mordiscos en el borde no la bajan.
#   - fruta redonda u ovalada vista desde arriba: 0,80 a 0,95
#   - fruta acostada (se ve como óvalo):          0,55 a 0,75
#   - dos frutas pegadas sin separar:             ~0,57
#   - tubos u objetos alargados:                  menos de 0,40
CIRCULARIDAD_MINIMA = 0.45       # para aceptar una fruta
CIRCULARIDAD_CALIBRACION = 0.70  # para calibrar (asegura que sea UNA sola fruta)

# Rango del color naranja en HSV.
# H = tono, S = saturación (qué tan "vivo" es el color), V = brillo.
# Naranja "fuerte": color vivo, sin dudas es fruta.
NARANJA_BAJO = np.array([0, 150, 100])
NARANJA_ALTO = np.array([25, 255, 255])
# El rojo también aparece al final de la escala de tono (170-180).
ROJO_BAJO = np.array([170, 150, 100])
ROJO_ALTO = np.array([180, 255, 255])
# Naranja "pálido": partes de la fruta quemadas por la luz (casi blancas).
# Solo se aceptan si están pegadas a una zona de naranja fuerte.
PALIDO_BAJO = np.array([5, 30, 220])
PALIDO_ALTO = np.array([30, 255, 255])

# Brillo mínimo de un hoyo para rellenarlo (el tallo es claro; el hueco
# negro que queda entre 3 frutas juntas es oscuro y NO se debe rellenar).
BRILLO_MINIMO_HOYO = 100

# Rango razonable de la escala (mm por píxel). Si una calibración da algo
# fuera de este rango, es porque se midió algo que no era una sola fruta.
ESCALA_MINIMA = 0.15
ESCALA_MAXIMA = 0.60
# Margen (px) para considerar que una fruta toca el borde de la zona.
MARGEN_BORDE = 6

CARPETA_FOTOS = "fotos"
ARCHIVO_CONFIG = "configuracion.json"

# ---------------- Detector con IA (Fase 2) ----------------
# False = detector por color (OpenCV).  True = modelo YOLO entrenado en Colab.
# Para usar YOLO: pip install ultralytics  y copiar best.pt a esta carpeta.
USAR_YOLO = True
MODELO_YOLO = "best.pt"
CONFIANZA_YOLO = 0.7     # probabilidad mínima para aceptar una detección (las naranjas dan 0,97 o más)
modelo_yolo = None       # se carga la primera vez que se usa


# ---------------- Guardar / cargar configuración ----------------
def guardar_configuracion():
    datos = {
        "escala_fondo": ESCALA_FONDO,
        "calibrado": CALIBRADO,
        "zona": [ZONA_X1, ZONA_Y1, ZONA_X2, ZONA_Y2],
    }
    with open(ARCHIVO_CONFIG, "w") as f:
        json.dump(datos, f, indent=2)
    print("Configuración guardada en", ARCHIVO_CONFIG)


def cargar_configuracion():
    global ESCALA_FONDO, CALIBRADO, ZONA_X1, ZONA_Y1, ZONA_X2, ZONA_Y2
    if not os.path.exists(ARCHIVO_CONFIG):
        print("Sin configuración guardada: se usa la escala estimada. Calibra con 'c'.")
        return
    with open(ARCHIVO_CONFIG) as f:
        datos = json.load(f)
    ZONA_X1, ZONA_Y1, ZONA_X2, ZONA_Y2 = datos["zona"]
    if ESCALA_MINIMA <= datos["escala_fondo"] <= ESCALA_MAXIMA:
        ESCALA_FONDO = datos["escala_fondo"]
        CALIBRADO = datos["calibrado"]
        print(f"Configuración cargada: escala = {ESCALA_FONDO:.4f} mm/px, zona = {datos['zona']}")
    else:
        print(f"La calibración guardada ({datos['escala_fondo']:.4f} mm/px) no es válida. Calibra de nuevo con 'c'.")


# ---------------- Medición ----------------
def diametro_en_mm(diametro_px, acostada=False):
    """
    Convierte el largo en píxeles a mm, corrigiendo la altura de la fruta.

    La parte más ancha de la fruta (su "ecuador") no está sobre el fondo,
    sino a una altura h = alto / 2, o sea más cerca de la cámara, y por eso
    se ve un poco más grande. El tamaño aparente es inversamente
    proporcional a la distancia, entonces:

        D = d_plano * (H - h) / H        con  h = RELACION * D / 2

    Despejando D:
        D = d_plano / (1 + d_plano * RELACION / (2 * H))

    Si la fruta está acostada, su parte más ancha queda a h = D / 2
    (RELACION = 1).
    """
    d_plano = diametro_px * ESCALA_FONDO     # medida como si la fruta fuera plana
    relacion = 1.0 if acostada else RELACION_ALTO_DIAMETRO
    return d_plano / (1 + d_plano * relacion / (2 * ALTURA_CAMARA_MM))


def calibrar(naranjas):
    """Calcula la escala del fondo usando la fruta mediana (tamaño conocido)."""
    global ESCALA_FONDO, CALIBRADO
    completas = [n for n in naranjas if n["completa"]]
    if len(completas) != 1:
        print(f"No se calibró: se ven {len(completas)} frutas completas en la zona. "
              "Deja SOLO la mediana, sin tocar otras frutas ni el borde.")
        return
    fruta = completas[0]
    if fruta["circularidad"] < CIRCULARIDAD_CALIBRACION:
        print(f"No se calibró: parece que hay más de una fruta pegada (circularidad "
              f"{fruta['circularidad']:.2f}). Separa la mediana de todo.")
        return

    h = ALTO_REFERENCIA_MM / 2
    # La mediana se ve como si midiera esto sobre el fondo:
    d_plano = DIAMETRO_REFERENCIA_MM * ALTURA_CAMARA_MM / (ALTURA_CAMARA_MM - h)
    escala = d_plano / fruta["largo_px"]
    if escala < ESCALA_MINIMA or escala > ESCALA_MAXIMA:
        print(f"No se calibró: la escala resultante ({escala:.4f} mm/px) no es razonable. "
              "Probablemente se midieron varias frutas juntas.")
        return

    ESCALA_FONDO = escala
    CALIBRADO = True
    print(f"Calibrado con una fruta de {fruta['largo_px']:.0f} px: "
          f"{ESCALA_FONDO:.4f} mm por píxel sobre el fondo")
    guardar_configuracion()


def clasificar(diametro_mm):
    if diametro_mm < LIMITE_CHICO_MM:
        return "chico"
    elif diametro_mm < LIMITE_GRANDE_MM:
        return "mediano"
    else:
        return "grande"


# ---------------- Detección ----------------
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


def crear_mascara(frame):
    """Imagen en blanco y negro: blanco = fruta dentro de la zona."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 1) Naranja fuerte (color vivo)
    fuerte = cv2.inRange(hsv, NARANJA_BAJO, NARANJA_ALTO)
    fuerte = cv2.bitwise_or(fuerte, cv2.inRange(hsv, ROJO_BAJO, ROJO_ALTO))

    # 2) Naranja pálido (partes quemadas por la luz). Una mancha pálida solo
    #    se acepta si está pegada a una zona de naranja fuerte; así se recupera
    #    la parte brillante de la fruta sin agregar papel, madera, etc.
    candidata = cv2.bitwise_or(fuerte, cv2.inRange(hsv, PALIDO_BAJO, PALIDO_ALTO))
    cantidad, etiquetas = cv2.connectedComponents(candidata)
    etiquetas_con_fruta = np.unique(etiquetas[fuerte > 0])
    etiquetas_con_fruta = etiquetas_con_fruta[etiquetas_con_fruta > 0]
    mascara = np.uint8(np.isin(etiquetas, etiquetas_con_fruta)) * 255

    # 3) Borrar todo lo que esté fuera de la zona de trabajo
    zona = np.zeros_like(mascara)
    zona[ZONA_Y1:ZONA_Y2, ZONA_X1:ZONA_X2] = 255
    mascara = cv2.bitwise_and(mascara, zona)

    # 4) Limpiar ruido y cerrar huecos pequeños
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))

    # 5) Rellenar los hoyos del tallo, pero NO el hueco negro entre 3 o más
    #    frutas juntas (si se rellena, las frutas se "pegan" y no se separan).
    #    El tallo es claro y el hueco entre frutas es oscuro: se mira el brillo.
    contornos, jerarquia = cv2.findContours(mascara, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    for i, c in enumerate(contornos):
        if jerarquia[0][i][3] == -1:      # no es un hoyo, es el borde exterior
            continue
        hoyo = np.zeros_like(mascara)
        cv2.drawContours(hoyo, [c], -1, 255, -1)
        area = cv2.countNonZero(hoyo)
        brillo = cv2.mean(hsv[:, :, 2], mask=hoyo)[0]
        if area < 600 or brillo >= BRILLO_MINIMO_HOYO:
            cv2.drawContours(mascara, [c], -1, 255, -1)
    return mascara


def separar_frutas(mascara):
    """
    Separa frutas que se tocan:
      1. La transformada de distancia indica, para cada píxel blanco,
         qué tan lejos está del borde. El centro de cada fruta es el punto
         más lejano, aunque dos frutas estén pegadas.
      2. Se toma como "semilla" la parte central de cada fruta (lo que está
         a más de la mitad de la distancia máxima del borde).
      3. Cada píxel de fruta se asigna a la semilla MÁS CERCANA. Como todas
         las semillas quedan a la misma distancia de su borde, la división
         cae justo en el "cuello" donde se tocan dos frutas.
    Devuelve una imagen de etiquetas (0 = fondo, 1, 2, 3, ... = cada fruta)
    y cuántas frutas encontró.
    """
    distancia = cv2.distanceTransform(mascara, cv2.DIST_L2, 5)
    if distancia.max() == 0:
        return None, 0

    # Semillas: zonas que están a más de la mitad de la distancia máxima del borde
    _, semillas = cv2.threshold(distancia, 0.5 * distancia.max(), 255, cv2.THRESH_BINARY)
    semillas = semillas.astype(np.uint8)

    # distanceTransformWithLabels busca, para cada píxel, el píxel en 0 más
    # cercano y devuelve a qué grupo pertenece. Por eso se invierten las
    # semillas (semilla = 0): así cada píxel recibe el número de su semilla más cercana.
    _, etiquetas = cv2.distanceTransformWithLabels(255 - semillas, cv2.DIST_L2, 5,
                                                   labelType=cv2.DIST_LABEL_CCOMP)
    etiquetas[mascara == 0] = 0          # el fondo no pertenece a ninguna fruta
    return etiquetas, int(etiquetas.max())


def corregir_perspectiva(puntos, cx, cy, centro_x, centro_y):
    """
    Lejos del centro de la imagen la cámara ve la fruta "en ángulo" y la
    fruta se ve estirada hacia afuera (en la dirección que apunta desde el
    centro de la imagen). Se mide en las pruebas: la misma fruta chica daba
    53,6 mm al centro y 57,6 mm en una esquina.

    El estiramiento es 1 / cos(angulo), donde el ángulo es la inclinación de
    la línea cámara-fruta. Para corregirlo, se "aplasta" el contorno en esa
    dirección multiplicándolo por cos(angulo).
    """
    dx, dy = cx - centro_x, cy - centro_y
    r = np.sqrt(dx ** 2 + dy ** 2)              # distancia al centro, en px
    if r < 1:
        return puntos
    ux, uy = dx / r, dy / r                     # dirección "hacia afuera"
    r_mm = r * ESCALA_FONDO
    cos_angulo = ALTURA_CAMARA_MM / np.sqrt(ALTURA_CAMARA_MM ** 2 + r_mm ** 2)

    px = puntos[:, 0] - cx
    py = puntos[:, 1] - cy
    radial = (px * ux + py * uy) * cos_angulo   # componente hacia afuera (se corrige)
    tangencial = -px * uy + py * ux             # componente de lado (no cambia)
    nuevos = np.zeros_like(puntos)
    nuevos[:, 0] = cx + radial * ux - tangencial * uy
    nuevos[:, 1] = cy + radial * uy + tangencial * ux
    return nuevos


def medir_fruta(c, frame):
    """
    Mide UNA fruta a partir de su contorno c (lista de puntos en la imagen).
    Sirve tanto para el detector por color como para los contornos de YOLO.
    Devuelve un diccionario con la medida, o None si la forma no parece fruta.
    """
    # Contorno envolvente: "estira una liga" alrededor de la fruta,
    # así los brillos o mordiscos del borde no afectan la medida.
    envolvente = cv2.convexHull(c)
    if len(envolvente) < 5:          # fitEllipse necesita al menos 5 puntos
        return None

    _, radio = cv2.minEnclosingCircle(envolvente)
    circularidad = cv2.contourArea(envolvente) / (np.pi * radio ** 2)
    if circularidad < CIRCULARIDAD_MINIMA:
        return None

    # Elipse ajustada: su eje mayor es el "largo" de la fruta, igual que
    # medirla con regla desde arriba. Sirve para frutas redondas, ovaladas
    # o acostadas. La elipse "elipse" es la que se ve (para dibujarla);
    # la medida se toma después de corregir la perspectiva.
    elipse = cv2.fitEllipse(envolvente)
    (x, y), _, _ = elipse
    alto_img, ancho_img = frame.shape[:2]
    puntos = envolvente.reshape(-1, 2).astype(np.float32)
    corregidos = corregir_perspectiva(puntos, x, y, ancho_img / 2, alto_img / 2)
    _, (eje1, eje2), _ = cv2.fitEllipse(corregidos)
    largo_px = max(eje1, eje2)
    acostada = min(eje1, eje2) / largo_px < RELACION_ACOSTADA

    # ¿Toca el borde de la zona? Entonces está cortada.
    bx, by, bw, bh = cv2.boundingRect(c)
    completa = not (bx <= ZONA_X1 + MARGEN_BORDE or by <= ZONA_Y1 + MARGEN_BORDE or
                    bx + bw >= ZONA_X2 - MARGEN_BORDE or by + bh >= ZONA_Y2 - MARGEN_BORDE)

    return {
        "contorno": envolvente.reshape(-1, 2),   # puntos del borde (para etiquetar con YOLO)
        "elipse": elipse,
        "x": int(x),
        "y": int(y),
        "largo_px": largo_px,
        "acostada": acostada,
        "circularidad": circularidad,
        "completa": completa,
    }


def buscar_naranjas_color(frame):
    """
    Detector por color (Fase 0).
    Devuelve la máscara y una lista de frutas. Cada fruta es un diccionario:
      "contorno"     -> puntos del borde de la fruta (contorno envolvente)
      "elipse"       -> elipse ajustada a la fruta (para dibujarla)
      "x", "y"       -> centro
      "largo_px"     -> largo de la fruta en píxeles (eje mayor de la elipse,
                        ya corregido por perspectiva)
      "acostada"     -> True si la fruta se ve muy ovalada (está de lado)
      "circularidad" -> qué tan "llena" es la forma (ver CIRCULARIDAD_MINIMA)
      "completa"     -> False si toca el borde de la zona (está cortada)
    """
    mascara = crear_mascara(frame)
    etiquetas, cantidad = separar_frutas(mascara)

    naranjas = []
    if etiquetas is None:
        return mascara, naranjas

    # Las frutas tienen etiquetas 1, 2, 3, ... (0 es el fondo)
    for numero in range(1, cantidad + 1):
        region = np.uint8(etiquetas == numero) * 255
        region = cv2.bitwise_and(region, mascara)

        contornos, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contornos) == 0:
            continue
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) < AREA_MINIMA:
            continue

        fruta = medir_fruta(c, frame)
        if fruta is not None:
            naranjas.append(fruta)
    return mascara, naranjas

    # Las frutas tienen etiquetas 1, 2, 3, ... (0 es el fondo)
    for numero in range(1, cantidad + 1):
        region = np.uint8(etiquetas == numero) * 255
        region = cv2.bitwise_and(region, mascara)

        contornos, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contornos) == 0:
            continue
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) < AREA_MINIMA:
            continue

        # Contorno envolvente: "estira una liga" alrededor de la fruta,
        # así los brillos o mordiscos del borde no afectan la medida.
        envolvente = cv2.convexHull(c)
        if len(envolvente) < 5:          # fitEllipse necesita al menos 5 puntos
            continue

        _, radio = cv2.minEnclosingCircle(envolvente)
        circularidad = cv2.contourArea(envolvente) / (np.pi * radio ** 2)
        if circularidad < CIRCULARIDAD_MINIMA:
            continue

        # Elipse ajustada: su eje mayor es el "largo" de la fruta, igual que
        # medirla con regla desde arriba. Sirve para frutas redondas, ovaladas
        # o acostadas. La elipse "elipse" es la que se ve (para dibujarla);
        # la medida se toma después de corregir la perspectiva.
        elipse = cv2.fitEllipse(envolvente)
        (x, y), _, _ = elipse
        alto_img, ancho_img = frame.shape[:2]
        puntos = envolvente.reshape(-1, 2).astype(np.float32)
        corregidos = corregir_perspectiva(puntos, x, y, ancho_img / 2, alto_img / 2)
        _, (eje1, eje2), _ = cv2.fitEllipse(corregidos)
        largo_px = max(eje1, eje2)
        acostada = min(eje1, eje2) / largo_px < RELACION_ACOSTADA

        # ¿Toca el borde de la zona? Entonces está cortada.
        bx, by, bw, bh = cv2.boundingRect(c)
        completa = not (bx <= ZONA_X1 + MARGEN_BORDE or by <= ZONA_Y1 + MARGEN_BORDE or
                        bx + bw >= ZONA_X2 - MARGEN_BORDE or by + bh >= ZONA_Y2 - MARGEN_BORDE)

        naranjas.append({
            "contorno": envolvente.reshape(-1, 2),   # puntos del borde (para etiquetar con YOLO)
            "elipse": elipse,
            "x": int(x),
            "y": int(y),
            "largo_px": largo_px,
            "acostada": acostada,
            "circularidad": circularidad,
            "completa": completa,
        })
    return mascara, naranjas


def buscar_naranjas_yolo(frame):
    """
    Detector con IA (Fase 2): el modelo YOLO encuentra el contorno de cada
    naranja dentro de la zona de trabajo, y la medida se calcula igual que
    con el detector por color (medir_fruta).
    """
    global modelo_yolo
    if modelo_yolo is None:
        from ultralytics import YOLO
        modelo_yolo = YOLO(MODELO_YOLO)

    recorte = frame[ZONA_Y1:ZONA_Y2, ZONA_X1:ZONA_X2]
    resultado = modelo_yolo.predict(recorte, conf=CONFIANZA_YOLO, retina_masks=True, verbose=False)[0]

    mascara = np.zeros(frame.shape[:2], np.uint8)
    naranjas = []
    if resultado.masks is None:
        return mascara, naranjas

    for poligono in resultado.masks.xy:          # un polígono por naranja (en el recorte)
        if len(poligono) < 5:
            continue
        c = poligono.copy()
        c[:, 0] += ZONA_X1                       # volver a coordenadas de la imagen completa
        c[:, 1] += ZONA_Y1
        c = c.astype(np.int32).reshape(-1, 1, 2)
        cv2.drawContours(mascara, [c], -1, 255, -1)
        if cv2.contourArea(c) < AREA_MINIMA:
            continue
        fruta = medir_fruta(c, frame)
        if fruta is not None:
            naranjas.append(fruta)
    return mascara, naranjas


def buscar_naranjas(frame):
    """Usa el detector elegido en USAR_YOLO."""
    if USAR_YOLO:
        return buscar_naranjas_yolo(frame)
    return buscar_naranjas_color(frame)


# ---------------- Programa principal ----------------
if __name__ == "__main__":
    cargar_configuracion()
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
    contador_fotos = len(os.listdir(CARPETA_FOTOS))   # para no sobrescribir fotos anteriores

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
        for fruta in naranjas:
            x, y = fruta["x"], fruta["y"]
            arriba = int(y - fruta["largo_px"] / 2) - 10     # posición del texto

            if not fruta["completa"]:
                # Fruta cortada por el borde de la zona: se marca en rojo y no se cuenta
                cv2.ellipse(frame, fruta["elipse"], (0, 0, 255), 2)
                cv2.putText(frame, "incompleta", (x - 60, arriba),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                continue

            largo_mm = diametro_en_mm(fruta["largo_px"], fruta["acostada"])
            categoria = clasificar(largo_mm)
            conteo[categoria] += 1

            texto = f"{largo_mm:.1f} mm ({fruta['largo_px']:.0f} px) - {categoria}"
            cv2.ellipse(frame, fruta["elipse"], (0, 255, 0), 2)
            cv2.putText(frame, texto, (x - 100, arriba),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Resumen arriba a la izquierda
        resumen = f"Chicas: {conteo['chico']}  Medianas: {conteo['mediano']}  Grandes: {conteo['grande']}"
        cv2.putText(frame, resumen, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        detector = "IA (YOLO)" if USAR_YOLO else "color"
        if CALIBRADO:
            cv2.putText(frame, f"Calibrado - detector: {detector}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "SIN CALIBRAR (escala estimada) - presiona c con la mediana",
                        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("Clasificador", frame)
        cv2.imshow("Mascara", mascara)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord('q'):
            break
        elif tecla == ord('c'):
            calibrar(naranjas)
        elif tecla == ord('z'):
            print("Arrastra un rectángulo sobre la superficie negra y presiona Enter (Esc = cancelar)")
            x, y, w, h = cv2.selectROI("Clasificador", original, showCrosshair=False)
            if w > 0 and h > 0:
                ZONA_X1, ZONA_Y1, ZONA_X2, ZONA_Y2 = x, y, x + w, y + h
                guardar_configuracion()
        elif tecla == ord('m'):
            print("---- Medidas actuales ----")
            for i, fruta in enumerate(naranjas, start=1):
                if not fruta["completa"]:
                    print(f"Fruta {i}: incompleta (toca el borde de la zona)  "
                          f"(posición x={fruta['x']}, y={fruta['y']})")
                    continue
                largo_mm = diametro_en_mm(fruta["largo_px"], fruta["acostada"])
                acostada = "  (acostada)" if fruta["acostada"] else ""
                print(f"Fruta {i}: {largo_mm:.1f} mm ({fruta['largo_px']:.0f} px)  {clasificar(largo_mm)}{acostada}"
                      f"  circularidad {fruta['circularidad']:.2f}  (posición x={fruta['x']}, y={fruta['y']})")
        elif tecla == ord('s'):
            ruta = os.path.join(CARPETA_FOTOS, f"naranja_{contador_fotos:04d}.jpg")
            cv2.imwrite(ruta, original)
            contador_fotos += 1
            print("Guardada:", ruta)

    cap.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)   # en macOS/Spyder ayuda a que las ventanas se cierren de verdad
