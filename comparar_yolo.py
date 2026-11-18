"""
Fase 3 - Comparar el detector por color con el detector YOLO
------------------------------------------------------------
Pasa todas las fotos de la carpeta "fotos" por los dos detectores y compara,
fruta por fruta, el largo medido (mm) y la categoría.

Uso (en la carpeta Clasificador, con el venv activado y best.pt en la carpeta):
    python3 comparar_yolo.py
"""

import os
import cv2
import numpy as np

import clasificador_naranjas as cn
from generar_dataset import zona_de_la_foto, numero_de_foto

DISTANCIA_MAXIMA = 40     # px: dos detecciones son la misma fruta si sus centros están así de cerca


def emparejar(lista_color, lista_yolo):
    """Junta cada fruta del detector por color con la fruta YOLO más cercana."""
    pares = []
    usadas = set()
    for fc in lista_color:
        mejor, mejor_d = None, DISTANCIA_MAXIMA
        for j, fy in enumerate(lista_yolo):
            d = np.hypot(fc["x"] - fy["x"], fc["y"] - fy["y"])
            if j not in usadas and d < mejor_d:
                mejor, mejor_d = j, d
        if mejor is not None:
            usadas.add(mejor)
            pares.append((fc, lista_yolo[mejor]))
    return pares


if __name__ == "__main__":
    cn.cargar_configuracion()
    nombres = sorted(f for f in os.listdir(cn.CARPETA_FOTOS) if f.endswith(".jpg"))

    diferencias = []
    misma_categoria = 0
    total_color = total_yolo = 0

    for nombre in nombres:
        img = cv2.imread(os.path.join(cn.CARPETA_FOTOS, nombre))
        cn.ZONA_X1, cn.ZONA_Y1, cn.ZONA_X2, cn.ZONA_Y2 = zona_de_la_foto(numero_de_foto(nombre))

        _, color = cn.buscar_naranjas_color(img)
        _, yolo = cn.buscar_naranjas_yolo(img)
        color = [f for f in color if f["completa"]]
        yolo = [f for f in yolo if f["completa"]]
        total_color += len(color)
        total_yolo += len(yolo)

        print(f"{nombre}: color {len(color)} frutas, YOLO {len(yolo)} frutas")
        for fc, fy in emparejar(color, yolo):
            mm_c = cn.diametro_en_mm(fc["largo_px"], fc["acostada"])
            mm_y = cn.diametro_en_mm(fy["largo_px"], fy["acostada"])
            cat_c, cat_y = cn.clasificar(mm_c), cn.clasificar(mm_y)
            diferencias.append(mm_y - mm_c)
            misma_categoria += cat_c == cat_y
            marca = "" if cat_c == cat_y else "   <-- distinta categoría"
            print(f"    ({fc['x']:4d},{fc['y']:4d})  color {mm_c:5.1f} mm {cat_c:8s} | "
                  f"YOLO {mm_y:5.1f} mm {cat_y:8s}{marca}")

    print("\n---- Resumen ----")
    print(f"Frutas completas detectadas: color {total_color}, YOLO {total_yolo}")
    if diferencias:
        diferencias = np.array(diferencias)
        print(f"Frutas comparadas: {len(diferencias)}")
        print(f"Diferencia promedio (YOLO - color): {diferencias.mean():+.2f} mm")
        print(f"Diferencia absoluta promedio:       {np.abs(diferencias).mean():.2f} mm")
        print(f"Misma categoría: {misma_categoria} de {len(diferencias)}")
