# 🍓 Guía de la Raspberry Pi — Estación 3

## 1. Qué pedir

| Artículo | Recomendación | Por qué |
|---|---|---|
| Raspberry Pi | **Raspberry Pi 5, 4 GB u 8 GB** | Es 2 a 3 veces más rápida que la Pi 4 para visión e IA. Una Pi 4 (4 GB) también sirve, pero más lenta. |
| Fuente de poder | **Oficial de 27 W USB-C** (para Pi 5) | Con un cargador de celular se apaga o se pone lenta cuando trabaja fuerte. |
| Tarjeta microSD | 32 o 64 GB, clase **A2** | Ahí va el sistema y el programa. |
| Ventilador | **Active Cooler** oficial (Pi 5) o carcasa con ventilador | Procesar video todo el rato la calienta; sin ventilador baja su velocidad. |
| Cable micro-HDMI a HDMI | 1 | La Pi 5 usa micro-HDMI, para mostrar el programa en un monitor el día de la presentación. |
| Cámara | La misma **LINK ON** por USB | Con la misma cámara, el modelo y la calibración siguen sirviendo. |
| Red | Cable de red o WiFi del router | Para enviar los datos a las estaciones 4 y 5. |
| Marcador | `marcador_calibracion.pdf` impreso a tamaño real | Autocalibración (ver más abajo). |

## 2. Instalar el sistema

1. En otro computador, instalar **Raspberry Pi Imager** y grabar en la microSD **Raspberry Pi OS (64-bit)** con escritorio.
2. En las opciones del Imager, definir: nombre `estacion3`, usuario y contraseña, WiFi del router y activar SSH.
3. Poner la microSD en la Pi, conectar cámara, monitor, teclado y la fuente de poder.

## 3. Instalar el programa

En la terminal de la Raspberry:

```bash
sudo apt update
sudo apt install -y git python3-venv
git clone https://github.com/PackIA-Coquimbo/estacion3.git
cd estacion3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-raspberry.txt
chmod +x iniciar_estacion3.sh
```

La instalación puede tardar 15 a 30 minutos (descarga PyTorch).

## 4. Configurar

En `estacion3_cinta.py`:

```python
URL_ESTACION4 = "http://IP_DE_LA_ESTACION_4:PUERTO/fruta"
URL_ESTACION5 = "http://IP_DE_LA_ESTACION_5:PUERTO/fruta"
DIRECCION = "derecha"        # o "izquierda", según cómo avance la cinta en la imagen
```

Para usar YOLO en la Raspberry, en `clasificador_naranjas.py`:

```python
USAR_YOLO = True
MODELO_YOLO = "best_ncnn_model"   # versión optimizada para Raspberry
```

- **Cámara:** si no abre, revisar el número con `v4l2-ctl --list-devices` y cambiar `CAMARA` en `clasificador_naranjas.py`.
- **IP de la Raspberry:** se ve con `hostname -I`. Conviene pedir en el router una IP fija (reserva DHCP) para cada estación.
- **Zona de trabajo:** se ajusta una vez con `python3 clasificador_naranjas.py` y la tecla `z`, encerrando la cinta. Queda guardada en `configuracion.json`.

## 5. Autocalibración (día de la presentación)

1. Imprimir `marcador_calibracion.pdf` a **tamaño real (100 %)** y comprobar con regla que el cuadrado mida 60 mm. Si mide otra cosa, anotar la medida en `TAMANO_MARCADOR_MM` (en `autocalibracion.py`).
2. Pegarlo **al costado de la cinta, a la misma altura que la superficie de la cinta**, dentro de la imagen pero fuera del camino de las naranjas.
3. Comprobar con `python3 autocalibracion.py probar`: debe aparecer en verde con la escala medida.

Al iniciar `estacion3_cinta.py`, el programa encuentra el marcador y se calibra solo. Después lo revisa cada cierto tiempo y se recalibra si la cámara se movió. En pantalla aparece *"Autocalibrado con marcador"*.

## 6. Que parta solo al encender

Crear el archivo `~/.config/autostart/estacion3.desktop` con:

```ini
[Desktop Entry]
Type=Application
Name=Estacion 3
Exec=/home/USUARIO/estacion3/iniciar_estacion3.sh
```

(cambiar `USUARIO` por el usuario de la Raspberry). Al reiniciar, la ventana del programa debería abrirse sola. Esto depende de la versión de Raspberry Pi OS, así que hay que comprobarlo con la Raspberry.

## 7. Revisar la velocidad

```bash
python3 medir_velocidad.py
```

Referencia medida en el MacBook (procesador, sin GPU):

| Detector | Tiempo por imagen | Imágenes por segundo |
|---|---|---|
| Por color | 32 ms | 32 |
| YOLO PyTorch (`best.pt`) | 54 ms | 19 |
| YOLO NCNN (`best_ncnn_model`) | 42 ms | 24 |

La Raspberry será varias veces más lenta. Como estimación, entre 4 y 8 imágenes por segundo, a confirmar con este script en la Raspberry. Con la cinta lenta debería bastar: a 5 imágenes por segundo y una cinta de 5 cm/s, cada naranja se alcanza a medir unas 9 veces completa antes de la línea de decisión.
