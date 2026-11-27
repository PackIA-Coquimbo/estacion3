# App de la Estación 3 — diseño

## Para qué

Hoy la Estación 3 son tres programas separados (`clasificador_naranjas.py`, `estacion3_cinta.py`, `simulador_estaciones.py`). Para probar hay que abrir varias terminales, activar el entorno en cada una y recordar teclas. El equipo quiere **una sola app con tres pestañas** para **probar y ajustar** el sistema, y que de paso sirva para **mostrar en pantalla lo que está pasando** (por ejemplo en la presentación). Debe funcionar igual en el MacBook y en la Raspberry Pi.

## Objetivos

- Un solo comando abre todo: `python3 app_estacion3.py`, y la app se ve en el navegador (`http://localhost:8000`).
- Tres pestañas, como en Chrome:
  1. **Clasificador:** cámara con las naranjas medidas, calibrar con la naranja mediana, elegir la zona arrastrando el mouse sobre la imagen, guardar foto, ver la máscara y una tabla con las medidas actuales.
  2. **Estación cinta:** seguimiento de naranjas, línea de decisión que se mueve con un clic, dirección de la cinta (4 flechas), grabar video, contadores, lista de las últimas naranjas, estado de la autocalibración y direcciones de las estaciones 4 y 5.
  3. **Simulador:** encender y apagar las estaciones 4 y 5 simuladas, y ver lo que recibe cada una (posición del servo y contadores del dashboard).
- La cámara se abre **una sola vez** y las pestañas la comparten.
- Los ajustes (zona, calibración, línea, dirección, direcciones de las estaciones) se guardan y se recuperan al volver a abrir.
- Se puede abrir desde otro computador del mismo router (`http://IP_DE_LA_RASPBERRY:8000`).

## Fuera de alcance

- Generar el dataset y entrenar YOLO: siguen siendo los scripts actuales.
- Reemplazar el software de las estaciones 4 y 5.
- Usuarios y contraseñas.

## Lo que haría fracasar la app aunque "funcione"

- Que la clasificación dependa de que la página esté abierta, o que el video en la página la haga más lenta.
- Que las naranjas que se mueven al calibrar se envíen como si fueran de la cinta.
- Romper los programas actuales: deben seguir funcionando solos.

## Restricciones

- Python 3.9 en el Mac (venv actual) y Raspberry Pi OS de 64 bits en la Raspberry.
- Una sola cámara USB (LINK ON) a 1920 × 1080.
- La Raspberry tiene poco procesador: hay que procesar cada imagen una sola vez y enviar al navegador una versión más chica.
- Código legible para el equipo (nivel pregrado), en español y con comentarios, como el resto del proyecto.

## Formas consideradas

| Forma | A favor | En contra |
|---|---|---|
| **A. App en el navegador (Flask)** — *elegida* | Igual en Mac y Raspberry; se puede ver desde otro computador; la más fácil de pulir visualmente; el simulador entra sin esfuerzo porque ya todo es HTTP | Una librería más (Flask); el video en la página llega con unas décimas de retraso (no afecta la clasificación) |
| B. Ventana de escritorio (Tkinter) | Solo Python | El Tkinter del Python del Mac es antiguo y suele fallar en macOS nuevos; se ve anticuada; solo se ve en la pantalla de la Raspberry |
| C. Ampliar la ventana de OpenCV | Cambio mínimo | No son pestañas reales; mover la línea y elegir la zona sigue siendo incómodo |

El equipo eligió la **A**.

## Cómo funciona

```
                cámara (o video)
                      │
             ┌────────▼─────────┐
             │  MOTOR (hilo)    │  lee una imagen, detecta y mide una vez,
             │                  │  sigue las naranjas, decide en la línea,
             │                  │  autocalibra, graba video
             └──┬──────────┬────┘
   envía calibre│          │ última imagen + estado
                ▼          ▼
   estaciones 4 y 5     SERVIDOR WEB (Flask, puerto 8000)
   (reales o las          ├─ /video/clasificador  ┐ video para cada pestaña
    simuladas dentro      ├─ /video/cinta         ┘
    de la misma app)      ├─ /api/...  botones y ajustes
                          └─ /sim/estacion4/fruta, /sim/estacion5/fruta
                                    │
                               NAVEGADOR (3 pestañas)
```

- **Motor:** un hilo que corre siempre, con la página abierta o cerrada. Reutiliza las funciones que ya existen (`clasificador_naranjas`, `estacion3_cinta`, `autocalibracion`) para no duplicar la lógica.
- **Video:** el motor dibuja la vista de cada pestaña sobre la última imagen y la envía achicada (unos 960 px de ancho) como video MJPEG. Solo se dibuja la vista que alguien está mirando.
- **Simulador:** son dos rutas dentro de la misma app. Al encenderlo, el motor envía a esas rutas; al apagarlo, envía a las direcciones reales de las estaciones 4 y 5.
- **Envío pausable:** un interruptor "Envío a estaciones" en el encabezado. Si está pausado, la línea sigue funcionando en pantalla, pero no se envía nada ni se cuenta.
- **Ajustes:** la zona y la escala siguen en `configuracion.json` (las mismas que usan los otros programas); la dirección, la línea, las direcciones de las estaciones y el detector van en `configuracion_cinta.json`.

## Pantalla (boceto)

```
┌───────────────────────────────────────────────────────────────────┐
│ 🍊 Estación 3 · PackIA   ● Calibrado 0,2916 mm/px  18 img/s  [Envío ON] │
│ [ Clasificador ] [ Estación cinta ] [ Simulador ]                 │
├──────────────────────────────────────────┬────────────────────────┤
│                                          │ Total 15               │
│          video de la cámara              │ Chicas 0  Medianas 8   │
│     (clic = mover línea de decisión)     │ Grandes 7  Revisión 0  │
│                                          │ Dirección: ↑ ↓ ← →     │
│                                          │ [● Grabar] [Reiniciar] │
│                                          │ Últimas: #17 60,3 med  │
└──────────────────────────────────────────┴────────────────────────┘
```

## Archivos

- `app_estacion3.py` — servidor y motor.
- `templates/index.html`, `static/app.js`, `static/estilo.css` — la página.
- `requirements.txt` y `requirements-raspberry.txt` — se agrega `flask`.

## Decisiones tomadas por Claude (el equipo puede cambiarlas)

- El interruptor de **pausar el envío**, para calibrar sin mandar naranjas por error.
- Video del navegador a ~960 px de ancho, para no cargar la Raspberry.
- Puerto 8000 para la app (el 5000 lo ocupa AirPlay en macOS).
- Estilo visual: oscuro con acentos naranjos, coherente con la presentación del proyecto.
- Los programas actuales se mantienen sin cambios de comportamiento.

## Lo que queda a criterio de quien lo construya

- Detalles de diseño visual y orden de los botones dentro de cada pestaña.
- Cada cuánto se actualizan los contadores en la página (bastan 2 a 4 veces por segundo).
