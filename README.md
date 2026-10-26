# 🍊 Estación 3: Calibre, uniformidad y consistencia

Módulo de análisis físico del lote de naranjas. Evalúa si la caja presenta **coherencia física** para su clasificación comercial.

## 📋 Resumen de la estación

| Estación | Grupo | Función principal | Enfoque de IA |
|---|---|---|---|
| **3. Calibre, uniformidad y consistencia** | 3 estudiantes | Evaluar tamaño, llenado, peso y coherencia física | Análisis de variables físicas e imagen |

**Problema de IA:** determinar si el lote es consistente en cuanto a tamaño, llenado, peso y coherencia general.

**Salida esperada:** clasificar el lote como `consistente`, `irregular`, `subllenado`, `peso inconsistente` o `revisión`, y entregar la evaluación de consistencia a la **Estación 4**.

---

## 🚦 Estado de avance

| # | Actividad | Estado | Notas |
|---|---|---|---|
| 1 | Diseñar el módulo de análisis físico del lote | 🔄 En proceso | Fase 0 implementada: detección y medición por visión computacional |
| 2 | Registrar el peso real, simulado o medido (balanza o cámara) | ⏳ Pendiente | Aún no hay lectura ni simulación de peso en el código |
| 3 | Capturar una imagen de la caja (arriba o de frente) | ✅ Terminada | Webcam fija sobre el marco; tecla `s` guarda fotos |
| 4 | Definir variables (peso, llenado, nº de frutas, uniformidad, coherencia imagen/peso) | 🔄 En proceso | Ya se mide el **diámetro** y se cuentan las frutas; faltan peso, llenado y uniformidad |
| 5 | Construir tabla de datos con variables físicas e indicadores visuales | ⏳ Pendiente | Hoy los resultados solo se muestran en pantalla |
| 6 | Clasificar el lote (consistente / irregular / subllenado / peso inconsistente / revisión) | 🔄 En proceso | Por ahora se clasifica **cada fruta** en chico / mediano / grande, no el lote completo |
| 7 | Entregar evaluación de consistencia a la Estación 4 | ⏳ Pendiente | Depende de los puntos 4, 5 y 6 |

### Avances técnicos ya logrados

| Componente | Estado |
|---|---|
| Detección de naranjas por color (HSV) dentro de la zona de trabajo | ✅ Terminada |
| Separación de frutas que se tocan (watershed) | ✅ Terminada |
| Filtro por área mínima y circularidad (descarta manchas) | ✅ Terminada |
| Calibración px → mm con una naranja de referencia (tecla `c`) | ✅ Terminada |
| Clasificación por calibre (chico / mediano / grande) | ✅ Terminada |
| Guardado de imágenes para dataset (tecla `s`) | 🔄 En proceso |
| Entrenamiento de un modelo de IA (Fase 2) | ⏳ Pendiente |
| Clasificación por peso mediante balanza | ⚠️ Posiblemente descartada |

> **Leyenda:** ✅ Terminada · 🔄 En proceso · ⏳ Pendiente · ⚠️ Posiblemente descartada

---

## 🛠️ Tecnologías utilizadas

| Tecnología | Uso |
|---|---|
| **Python** | Lenguaje principal del proyecto (por ahora, lo único utilizado) |
| **OpenCV** (`opencv-python`) | Captura de video, segmentación por color, watershed, medición |
| **NumPy** | Manejo de matrices e imágenes |
| **Webcam externa LINK ON (USB)** | Captura de imagen, fija sobre el marco de PVC a altura oficial |

---

## ⚙️ Cómo funciona (Fase 0, sin entrenamiento)

1. La webcam captura la caja dentro de la **zona de trabajo** (marco de PVC); lo que queda fuera se ignora.
2. Se crea una **máscara de color naranja/rojo** en espacio HSV.
3. Se **separan las naranjas que se tocan** con la transformada de distancia y watershed.
4. Se filtran las manchas por área y circularidad, y se mide el **diámetro** de cada fruta.
5. Se clasifica cada una como **chico / mediano / grande**, en píxeles o en mm si está calibrado.

## ▶️ Cómo ejecutarlo

```bash
pip install opencv-python numpy
python clasificador_naranjas.py
```

| Tecla | Acción |
|---|---|
| `c` | Calibrar (una sola naranja de 60 mm dentro del marco) |
| `s` | Guardar la imagen actual en `fotos/` (para el dataset de la fase 2) |
| `q` | Salir |

### Parámetros principales

Se ajustan al inicio de [clasificador_naranjas.py](clasificador_naranjas.py):

- `CAMARA`: índice de la webcam (el programa lista las disponibles al iniciar).
- `ZONA_X1`, `ZONA_Y1`, `ZONA_X2`, `ZONA_Y2`: zona de trabajo en píxeles.
- `LIMITE_CHICO_PX` / `LIMITE_GRANDE_PX`: límites de calibre en píxeles.
- `LIMITE_CHICO_MM` / `LIMITE_GRANDE_MM`: límites de calibre en mm (tras calibrar).
- `MM_POR_PIXEL`: valor obtenido al calibrar con `c`.

---

## 🔭 Próximos pasos

- [ ] Registrar el peso del lote (balanza, cámara o simulado).
- [ ] Calcular uniformidad de tamaño y nivel de llenado de la caja.
- [ ] Generar la tabla de datos (CSV) con las variables físicas.
- [ ] Clasificar el lote completo (consistente, irregular, subllenado, peso inconsistente, revisión).
- [ ] Enviar la evaluación a la Estación 4.
