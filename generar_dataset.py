"""
Fase 1 - Generar el dataset para YOLO de forma automática
---------------------------------------------------------
Usa el detector actual (clasificador_naranjas.py) para encontrar el contorno
de cada naranja en las fotos de la carpeta "fotos" y guarda las etiquetas en
el formato de YOLO para segmentación. Así no hay que dibujar a mano el borde
de cada fruta: solo hay que REVISAR que las etiquetas estén bien.

Cada foto se recorta a la zona de trabajo (la superficie negra), porque
el modelo solo debe aprender lo que pasa sobre la cinta.

Uso (en la carpeta Clasificador, con el venv activado):
    python3 generar_dataset.py

Resultado:
    dataset_naranjas/
        images/train/   images/val/     -> fotos recortadas
        labels/train/   labels/val/     -> un .txt por foto con los polígonos
        revision/                       -> fotos con el contorno dibujado (para revisar)
        data.yaml                       -> archivo que lee YOLO

Formato de cada línea del .txt (YOLO segmentación):
    clase x1 y1 x2 y2 x3 y3 ...     (coordenadas entre 0 y 1)
"""

import os
import shutil
import cv2
import numpy as np

import clasificador_naranjas as cn   # reutiliza el detector y la zona guardada

# ---------------- Configuración ----------------
CARPETA_FOTOS = "fotos"
CARPETA_DATASET = "dataset_naranjas"

# Si se presionó "s" varias veces sin mover las frutas, las fotos son casi
# iguales ("misma escena"). Todas las fotos de una escena van juntas a
# entrenamiento o a validación, así el modelo nunca se evalúa con una foto
# casi idéntica a una que ya vio. Con True se deja solo una foto por escena.
QUITAR_REPETIDAS = False
DIFERENCIA_MINIMA = 5.0      # diferencia promedio de color para considerar otra escena

# 1 de cada 5 escenas va a validación (fotos que el modelo NO ve al entrenar)
CADA_CUANTAS_VALIDACION = 5

# Zonas especiales para fotos antiguas sacadas con otra posición de la cámara.
# (primera foto, última foto): [x1, y1, x2, y2]
# Las fotos que no están aquí usan la zona de configuracion.json.
ZONAS_ESPECIALES = {
    (0, 9): [500, 0, 1450, 990],        # 30 de octubre, primer montaje
    (10, 13): [519, 64, 1431, 1001],    # 6 de noviembre, antes de ajustar la zona
    (14, 26): [565, 132, 1382, 953],
}


def zona_de_la_foto(numero):
    for (desde, hasta), zona in ZONAS_ESPECIALES.items():
        if desde <= numero <= hasta:
            return zona
    return [cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2]


def numero_de_foto(nombre):
    """'naranja_0012.jpg' -> 12"""
    return int(nombre.split("_")[-1].split(".")[0])


def agrupar_en_escenas(nombres):
    """Junta las fotos consecutivas casi iguales en una misma escena."""
    escenas = []
    anterior = None
    for nombre in nombres:
        img = cv2.imread(os.path.join(CARPETA_FOTOS, nombre))
        chica = cv2.resize(img, (192, 108)).astype(float)
        if anterior is None or np.abs(chica - anterior).mean() >= DIFERENCIA_MINIMA:
            escenas.append([nombre])          # escena nueva
        else:
            escenas[-1].append(nombre)        # misma escena que la foto anterior
        anterior = chica
    return escenas


def etiquetar_foto(nombre, carpeta_salida):
    """Recorta la foto, busca las naranjas y guarda imagen + etiquetas."""
    img = cv2.imread(os.path.join(CARPETA_FOTOS, nombre))

    # El detector trabaja con la zona que tenga configurada
    x1, y1, x2, y2 = zona_de_la_foto(numero_de_foto(nombre))
    cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2 = x1, y1, x2, y2
    _, naranjas = cn.buscar_naranjas_color(img)   # las etiquetas salen del detector por color

    recorte = img[y1:y2, x1:x2]
    alto, ancho = recorte.shape[:2]

    lineas = []
    revision = recorte.copy()
    for fruta in naranjas:
        puntos = fruta["contorno"].astype(np.float32)
        puntos[:, 0] -= x1                    # coordenadas dentro del recorte
        puntos[:, 1] -= y1
        puntos[:, 0] = np.clip(puntos[:, 0], 0, ancho - 1)
        puntos[:, 1] = np.clip(puntos[:, 1], 0, alto - 1)

        # Normalizar entre 0 y 1 (lo que pide YOLO)
        texto = " ".join(f"{px / ancho:.5f} {py / alto:.5f}" for px, py in puntos)
        lineas.append("0 " + texto)           # clase 0 = naranja

        color = (0, 255, 0) if fruta["completa"] else (0, 0, 255)
        cv2.polylines(revision, [puntos.astype(np.int32)], True, color, 3)

    base = os.path.splitext(nombre)[0]
    cv2.imwrite(os.path.join(CARPETA_DATASET, "images", carpeta_salida, base + ".jpg"), recorte)
    with open(os.path.join(CARPETA_DATASET, "labels", carpeta_salida, base + ".txt"), "w") as f:
        f.write("\n".join(lineas))
    cv2.putText(revision, f"{nombre}  ({carpeta_salida})  {len(naranjas)} naranjas",
                (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(CARPETA_DATASET, "revision", base + ".jpg"), revision)
    return len(naranjas)


# ---------------- Programa principal ----------------
if __name__ == "__main__":
    cn.cargar_configuracion()

    # Empezar de cero cada vez
    if os.path.exists(CARPETA_DATASET):
        shutil.rmtree(CARPETA_DATASET)
    for sub in ["images/train", "images/val", "labels/train", "labels/val", "revision"]:
        os.makedirs(os.path.join(CARPETA_DATASET, sub))

    nombres = sorted(f for f in os.listdir(CARPETA_FOTOS) if f.endswith(".jpg"))
    escenas = agrupar_en_escenas(nombres)
    print(f"{len(nombres)} fotos, {len(escenas)} escenas distintas")

    total = {"train": 0, "val": 0}
    for i, escena in enumerate(escenas):
        destino = "val" if i % CADA_CUANTAS_VALIDACION == 2 else "train"
        fotos = escena[:1] if QUITAR_REPETIDAS else escena
        for nombre in fotos:
            cantidad = etiquetar_foto(nombre, destino)
            total[destino] += 1
            print(f"  {nombre} -> {destino}: {cantidad} naranjas")

    with open(os.path.join(CARPETA_DATASET, "data.yaml"), "w") as f:
        f.write("path: .\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("names:\n")
        f.write("  0: naranja\n")

    print(f"Listo: {total['train']} fotos de entrenamiento y {total['val']} de validación.")
    print(f"Revisa las imágenes de '{CARPETA_DATASET}/revision' antes de entrenar.")
