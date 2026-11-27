# App de la Estación 3 — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una app en el navegador (Flask) con tres pestañas —Clasificador, Estación cinta y Simulador— que reemplaza abrir tres programas separados.

**Architecture:** Un objeto `Motor` procesa cada imagen una sola vez (detección, seguimiento, decisión en la línea, envío, autocalibración, grabación) reutilizando `clasificador_naranjas`, `estacion3_cinta` y `autocalibracion`. Un hilo lee la cámara o un video y alimenta al motor. Flask sirve la página, el video MJPEG de cada vista, una API JSON para botones y ajustes, y las rutas del simulador de las estaciones 4 y 5.

**Tech Stack:** Python 3.9 (venv de `~/Clasificador/venv` en el Mac), OpenCV, NumPy, requests, Flask, pytest; HTML + CSS + JavaScript sin librerías externas.

**Spec:** `docs/superpowers/specs/2026-11-27-app-estacion3-design.md`

## Global Constraints

- Un solo comando: `python3 app_estacion3.py [fuente]`; la app en `http://localhost:8000` y en `http://IP:8000` desde otro equipo (`host="0.0.0.0"`, puerto **8000**).
- La cámara (o video) se abre **una sola vez**; el motor corre aunque ninguna página esté abierta.
- Video al navegador achicado a **960 px** de ancho; solo se dibuja la vista pedida.
- Zona y escala siguen en `configuracion.json` (formato actual); dirección, línea, URLs, simulador y detector en `configuracion_cinta.json`.
- Interruptor "Envío a estaciones": pausado ⇒ no se envía ni se cuenta, la línea se sigue dibujando.
- Simulador dentro de la app en `/sim/estacion4/fruta` y `/sim/estacion5/fruta`; encendido ⇒ el motor envía a esas rutas; apagado ⇒ a las URLs reales.
- `clasificador_naranjas.py`, `estacion3_cinta.py`, `simulador_estaciones.py` y `autocalibracion.py` siguen funcionando solos, sin cambios de comportamiento.
- Código y textos en español, comentado, nivel pregrado. Estilo oscuro con acentos naranjos.

## Review Focus

1. **Calibrar con 0 o con 2+ naranjas en la zona:** la app debe responder con un mensaje claro y no cambiar la escala (hoy `cn.calibrar` solo imprime en la terminal).
2. **Zona dibujada al revés o muy chica** (arrastrar de abajo-derecha a arriba-izquierda, o un clic sin arrastrar): se normaliza; si mide menos de 100 px por lado o sale de la imagen, se rechaza con mensaje.
3. **Cámara que no abre o video que termina:** la página carga igual y muestra el aviso en el estado; un video se repite desde el inicio.
4. **Estación 4/5 apagada o URL equivocada:** el envío no bloquea el motor; el estado muestra cuántos envíos fallaron y el último error.
5. **Varias páginas abiertas a la vez** (Mac + proyector): ambos videos funcionan y el motor no se detiene ni se corrompe (acceso a la última imagen protegido con `threading.Lock`).

Además: al cambiar zona, línea o dirección se reinicia el seguimiento (no los contadores), para que una fruta no "cruce" por el cambio.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `motor_estacion3.py` (crear) | Clase `Motor`: estado, procesamiento por imagen, acciones, dibujo de vistas, configuración `configuracion_cinta.json` |
| `simulador_web.py` (crear) | Blueprint Flask del simulador y su estado |
| `app_estacion3.py` (crear) | Hilo de cámara, rutas Flask (página, video, API) y `main` |
| `templates/index.html`, `static/app.js`, `static/estilo.css` (crear) | La página con las 3 pestañas |
| `tests/test_motor.py`, `tests/test_simulador.py`, `tests/test_app.py` (crear) | Pruebas con pytest |
| `requirements.txt`, `requirements-raspberry.txt`, `.gitignore`, `README.md`, `docs/raspberry_pi.md` (modificar) | `flask`, `pytest`; ignorar `configuracion_cinta.json`; documentación |

Las pruebas usan `video_prueba_cinta.mp4` (3 naranjas que cruzan de izquierda a derecha: 52,9 / 66,2 / 61,9 mm) con la zona `[551, 134, 1400, 1007]` y la escala `0.2915604662874815`, fijadas en la prueba (no leídas de `configuracion.json`, que cambia al calibrar). Ninguna prueba escribe en `configuracion.json`: usar `tmp_path` como carpeta del motor y fijar `cn.ARCHIVO_CONFIG` a un archivo dentro de `tmp_path`.

---

### Task 1: Motor

**Files:**
- Create: `motor_estacion3.py`, `tests/test_motor.py`, `tests/conftest.py`
- Modify: `requirements.txt` (agregar `flask`, `pytest`), `requirements-raspberry.txt` (agregar `flask`), `.gitignore` (agregar `configuracion_cinta.json`, `.pytest_cache/`)

**Interfaces:**
- Consumes: `cn.buscar_naranjas(frame) -> (mascara, naranjas)`, `cn.diametro_en_mm`, `cn.clasificar`, `cn.guardar_configuracion`; `ec.actualizar_seguimiento`, `ec.avance`, `ec.calcular_linea`, `ec.cruzo_la_linea`, `ec.antes_de_la_linea`, `ec.decidir` (el motor fija `ec.DIRECCION` y `ec.POSICION_LINEA`); `ac.revisar(frame)`, `ac.ultima_escala`.
- Produces:
  - `Motor(enviar=None, carpeta=".")` — `enviar(datos: dict, destino: str) -> None` con `destino in ("estacion4", "estacion5")`; si es `None`, usa envío HTTP en hilos (como `ec.enviar`) a `url_estacion(destino)`.
  - `procesar(frame: np.ndarray) -> None`
  - `dibujar(vista: str, ancho: int = 960) -> bytes` — JPEG; `vista in ("clasificador", "cinta", "mascara")`
  - `estado() -> dict` con las claves: `calibrado, escala, autocalibrado, fps, envio_activo, direccion, posicion_linea, zona, conteo` (`chico, mediano, grande, revision, total`), `ultimas` (máx. 10 mensajes enviados, el más nuevo primero), `naranjas` (lista de `{"id","mm","calibre","completa"}` de la imagen actual), `grabando, simulador_activo, url_estacion4, url_estacion5, errores_envio, ultimo_error, mensaje_fuente, ancho_imagen, alto_imagen`
  - Acciones que devuelven `(ok: bool, mensaje: str)`: `calibrar()`, `fijar_zona(x1, y1, x2, y2)`, `fijar_linea(fraccion)`, `fijar_direccion(direccion)`, `fijar_urls(url4, url5)`
  - `fijar_envio(activo: bool)`, `fijar_simulador(activo: bool)`, `reiniciar()` (contadores, últimas y seguimiento), `guardar_foto() -> str` (ruta en `fotos/`), `alternar_grabacion() -> bool` (True si quedó grabando; archivos en `videos/`)
  - `url_estacion(destino) -> str`: con simulador activo `http://127.0.0.1:8000/sim/<destino>/fruta`, si no la URL configurada.
  - `PUERTO = 8000` (constante del módulo)

- [ ] **Step 1: Instalar dependencias de prueba**

Run: `source ~/Clasificador/venv/bin/activate && pip install flask pytest`
Expected: instala sin errores.

- [ ] **Step 2: Escribir las pruebas que fallan** (`tests/test_motor.py`; `conftest.py` agrega la carpeta del proyecto a `sys.path`)

```python
def test_video_envia_tres_naranjas_en_orden(motor_prueba):   # dirección "derecha", línea 0.6
    procesar_video(motor_prueba, "video_prueba_cinta.mp4")
    assert [d["calibre"] for d, destino in motor_prueba.enviados if destino == "estacion4"] == ["chico", "grande", "mediano"]
    assert motor_prueba.estado()["conteo"] == {"chico": 1, "mediano": 1, "grande": 1, "revision": 0, "total": 3}
    assert len([1 for d, destino in motor_prueba.enviados if destino == "estacion5"]) == 3

def test_envio_pausado_no_envia_ni_cuenta(motor_prueba):
    motor_prueba.fijar_envio(False)
    procesar_video(motor_prueba, "video_prueba_cinta.mp4")
    assert motor_prueba.enviados == [] and motor_prueba.estado()["conteo"]["total"] == 0

def test_calibrar_sin_una_sola_naranja_no_cambia_escala(motor_prueba):
    escala = motor_prueba.estado()["escala"]
    motor_prueba.procesar(imagen_vacia())          # zona sin naranjas
    ok, mensaje = motor_prueba.calibrar()
    assert not ok and "0" in mensaje and motor_prueba.estado()["escala"] == escala

def test_fijar_zona_normaliza_y_rechaza(motor_prueba):
    assert motor_prueba.fijar_zona(1400, 1007, 551, 134)[0] is True
    assert motor_prueba.estado()["zona"] == [551, 134, 1400, 1007]
    assert motor_prueba.fijar_zona(100, 100, 150, 150)[0] is False       # menos de 100 px
    assert motor_prueba.fijar_zona(0, 0, 2500, 900)[0] is False          # fuera de la imagen

def test_fijar_linea_y_direccion_validan(motor_prueba):
    assert motor_prueba.fijar_linea(0.77)[0] and not motor_prueba.fijar_linea(1.5)[0]
    assert motor_prueba.fijar_direccion("abajo")[0] and not motor_prueba.fijar_direccion("diagonal")[0]

def test_configuracion_cinta_persiste(tmp_path):
    m = Motor(enviar=lambda d, dest: None, carpeta=tmp_path); m.fijar_direccion("abajo"); m.fijar_linea(0.77)
    assert Motor(enviar=lambda d, dest: None, carpeta=tmp_path).estado()["direccion"] == "abajo"

def test_url_segun_simulador(motor_prueba):
    motor_prueba.fijar_urls("http://10.0.0.4:5004/fruta", "http://10.0.0.5:5005/fruta")
    motor_prueba.fijar_simulador(True)
    assert motor_prueba.url_estacion("estacion4") == "http://127.0.0.1:8000/sim/estacion4/fruta"
    motor_prueba.fijar_simulador(False)
    assert motor_prueba.url_estacion("estacion5") == "http://10.0.0.5:5005/fruta"

def test_dibujar_devuelve_jpeg_de_960(motor_prueba):
    motor_prueba.procesar(imagen_vacia())
    for vista in ("clasificador", "cinta", "mascara"):
        img = cv2.imdecode(np.frombuffer(motor_prueba.dibujar(vista), np.uint8), 1)
        assert img.shape[1] == 960
```

`motor_prueba` (fixture en `conftest.py`): `Motor` con `carpeta=tmp_path`, `enviar` que agrega `(datos, destino)` a `motor.enviados`, zona `[551, 134, 1400, 1007]`, escala `0.2915604662874815` con `cn.CALIBRADO = True`, dirección `"derecha"`, línea `0.6`, autocalibración desactivada. `procesar_video(motor, ruta)` lee todas las imágenes y llama `procesar`. `imagen_vacia()` = imagen 1920×1080 color `(40, 40, 40)`.

- [ ] **Step 3: Correr y ver que fallan**

Run: `python3 -m pytest tests/test_motor.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'motor_estacion3'`.

- [ ] **Step 4: Implementar `Motor` en `motor_estacion3.py`**

Misma lógica por imagen que el bucle de `estacion3_cinta.py` (seguir, medir antes de la línea, decidir al cruzar), pero: si `envio_activo` es False no envía ni cuenta; cada envío llama `enviar(datos, "estacion4")` y `enviar(datos, "estacion5")`; los errores del envío HTTP suman `errores_envio` y guardan `ultimo_error`. `calibrar()` revisa la cantidad de naranjas completas y la circularidad antes de llamar a `cn.calibrar`, y devuelve el mensaje (incluye la cantidad vista). Cambiar zona, línea o dirección vacía el seguimiento. Un `threading.Lock` protege la última imagen y las naranjas. `fps` = promedio de las últimas 30 imágenes. `dibujar` reutiliza los dibujos de `estacion3_cinta.py` (vista cinta) y de `clasificador_naranjas.py` (vista clasificador: elipse, mm, calibre).

- [ ] **Step 5: Correr y ver que pasan**

Run: `python3 -m pytest tests/test_motor.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add motor_estacion3.py tests/ requirements.txt requirements-raspberry.txt .gitignore
git commit -m "Motor de la app: procesamiento, acciones y vistas"
```

---

### Task 2: Simulador web

**Files:**
- Create: `simulador_web.py`, `tests/test_simulador.py`

**Interfaces:**
- Produces: `simulador = Blueprint("simulador", __name__)` con `POST /sim/estacion4/fruta` y `POST /sim/estacion5/fruta` (responden `{"ok": true}`; JSON inválido → 400); `estado_simulador() -> dict` con `{"estacion4": {"recibidas": int, "ultima": dict|None, "servo": str}, "estacion5": {"total","chico","mediano","grande","revision"}, "registro": [str, ...]}` (máx. 30 líneas, la más nueva primero); `reiniciar_simulador() -> None`. Servo: `chico → "izquierda"`, `mediano → "centro"`, `grande → "derecha"`, `revision → "sin mover"` (igual que `simulador_estaciones.py`).

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
def test_estacion4_mueve_servo(cliente):
    assert cliente.post("/sim/estacion4/fruta", json={"id": 1, "calibre": "grande"}).status_code == 200
    e = estado_simulador()["estacion4"]
    assert e["recibidas"] == 1 and e["servo"] == "derecha"

def test_estacion5_cuenta(cliente):
    for c in ["chico", "mediano", "mediano"]:
        cliente.post("/sim/estacion5/fruta", json={"id": 1, "calibre": c})
    assert estado_simulador()["estacion5"] == {"total": 3, "chico": 1, "mediano": 2, "grande": 0, "revision": 0}

def test_json_invalido_es_400(cliente):
    assert cliente.post("/sim/estacion4/fruta", data="hola").status_code == 400
```

`cliente`: app Flask mínima con el blueprint registrado; `reiniciar_simulador()` antes de cada prueba.

- [ ] **Step 2: Correr y ver que fallan** — Run: `python3 -m pytest tests/test_simulador.py -v` → FAIL (módulo no existe).
- [ ] **Step 3: Implementar `simulador_web.py`** con un `threading.Lock` para el estado.
- [ ] **Step 4: Correr y ver que pasan** — Expected: 3 passed.
- [ ] **Step 5: Commit** — `git commit -m "Simulador de las estaciones 4 y 5 dentro de la app"`

---

### Task 3: Servidor, hilo de cámara y página

**Files:**
- Create: `app_estacion3.py`, `templates/index.html`, `static/app.js`, `static/estilo.css`, `tests/test_app.py`

**Interfaces:**
- Consumes: `Motor` (Task 1), `simulador`, `estado_simulador` (Task 2).
- Produces: `crear_app(motor: Motor) -> Flask`; `iniciar_camara(motor: Motor, fuente) -> threading.Thread` (hilo demonio; `fuente` = número de cámara o ruta de video; un video se repite al terminar; si la cámara no abre, `motor.mensaje_fuente` lo dice y se reintenta cada 3 s). Rutas:
  - `GET /` → página; `GET /video/<vista>` → MJPEG (`multipart/x-mixed-replace; boundary=frame`), vista inválida → 404
  - `GET /api/estado` → `motor.estado()` + `"simulador": estado_simulador()`
  - `POST /api/calibrar`, `/api/zona` `{x1,y1,x2,y2}`, `/api/linea` `{fraccion}`, `/api/direccion` `{direccion}`, `/api/urls` `{url4,url5}`, `/api/envio` `{activo}`, `/api/simulador` `{activo}`, `/api/foto`, `/api/grabar`, `/api/reiniciar` → `{"ok": bool, "mensaje": str}`; datos faltantes o de tipo equivocado → 400 con mensaje
  - `main`: `python3 app_estacion3.py [fuente]` (por defecto `cn.CAMARA`), imprime `Abre http://localhost:8000` y la IP local, `app.run(host="0.0.0.0", port=8000, threaded=True)`.

- [ ] **Step 1: Escribir las pruebas que fallan** (`tests/test_app.py`, usando un `Motor` de prueba sin hilo de cámara y `app.test_client()`)

```python
def test_estado_tiene_claves(cliente):
    datos = cliente.get("/api/estado").get_json()
    assert {"conteo", "zona", "direccion", "simulador", "envio_activo"} <= set(datos)

def test_linea_y_direccion(cliente):
    assert cliente.post("/api/linea", json={"fraccion": 0.5}).get_json()["ok"]
    assert cliente.post("/api/direccion", json={"direccion": "diagonal"}).get_json()["ok"] is False

def test_zona_sin_datos_es_400(cliente):
    assert cliente.post("/api/zona", json={"x1": 10}).status_code == 400

def test_video_vista_invalida_es_404(cliente):
    assert cliente.get("/video/otra").status_code == 404

def test_simulador_recibe_envio_del_motor(cliente, motor_app):
    cliente.post("/api/simulador", json={"activo": True})
    assert motor_app.url_estacion("estacion4").endswith("/sim/estacion4/fruta")
```

- [ ] **Step 2: Correr y ver que fallan** — Run: `python3 -m pytest tests/test_app.py -v` → FAIL.
- [ ] **Step 3: Implementar `app_estacion3.py`.**
- [ ] **Step 4: Implementar la página** (`templates/index.html`, `static/app.js`, `static/estilo.css`):
  - Encabezado: nombre, estado de calibración (con "autocalibrado" si `autocalibrado`), img/s, aviso de `mensaje_fuente`, interruptor de envío.
  - Pestañas (la activa se recuerda en `localStorage` con `try/catch`); cada pestaña muestra su `<img src="/video/...">` y al cambiar de pestaña se cambia el `src` para no pedir videos ocultos.
  - **Clasificador:** botones Calibrar con mediana, Elegir zona (arrastrar sobre la imagen; se dibuja un rectángulo encima con un `<canvas>`; al soltar se envía en píxeles originales usando `ancho_imagen / img.clientWidth`), Guardar foto, Ver máscara (cambia la vista a `mascara`); tabla de `naranjas`.
  - **Estación cinta:** clic sobre la imagen → `/api/linea` con la fracción dentro de la zona según la dirección; 4 botones de dirección; Grabar (muestra REC), Reiniciar; contadores grandes; lista `ultimas`; campos de URLs con botón Guardar; errores de envío.
  - **Simulador:** interruptor encendido/apagado, tarjeta Estación 4 (servo y última fruta), tarjeta Estación 5 (contadores), registro.
  - Cada acción muestra su `mensaje` en un aviso pasajero. El estado se pide 3 veces por segundo.
  - Debe verse bien desde 1280 px de ancho (pantalla del Mac y de la Raspberry).
- [ ] **Step 5: Correr todas las pruebas** — Run: `python3 -m pytest -v` → Expected: 16 passed.
- [ ] **Step 6: Prueba manual con el video** — Run: `python3 app_estacion3.py video_prueba_cinta.mp4`, abrir `http://localhost:8000`, encender el simulador, poner dirección → y línea 0.6, y comprobar en la pestaña Simulador que llegan chico, grande y mediano; probar dibujar la zona y calibrar con el botón (debe decir cuántas naranjas ve). Comprobar con `curl -s localhost:8000/api/estado` que el contador sube.
- [ ] **Step 7: Commit** — `git commit -m "App de la Estación 3: servidor, cámara y página con 3 pestañas"`

---

### Task 4: Documentación y entrega

**Files:**
- Modify: `README.md` (sección "App de la Estación 3" al inicio de "Cómo ejecutarlo", fila en la estructura de archivos, captura en `docs/img/app_estacion3.png`), `docs/raspberry_pi.md` (iniciar con `python3 app_estacion3.py`; `iniciar_estacion3.sh` pasa a abrir la app).
- Modify: `iniciar_estacion3.sh` (ejecuta `app_estacion3.py`).

- [ ] **Step 1: Captura de la app** corriendo con el video, guardada en `docs/img/app_estacion3.png`.
- [ ] **Step 2: Actualizar README y guía de Raspberry.**
- [ ] **Step 3: Verificar que los programas antiguos siguen funcionando** — Run: `git diff HEAD~4 -- clasificador_naranjas.py estacion3_cinta.py simulador_estaciones.py autocalibracion.py` → sin cambios; y `python3 -c "import clasificador_naranjas, estacion3_cinta, autocalibracion, simulador_estaciones"` → sin errores.
- [ ] **Step 4: Commit y push** — `git commit -m "Documentación de la app" && git push origin main`
