"""
Simulador de las estaciones 4 y 5 (para probar sin los otros grupos)
--------------------------------------------------------------------
Levanta dos servidores HTTP en este computador:
  - Estación 4 (puerto 5004): recibe cada fruta y muestra hacia dónde movería el servo.
  - Estación 5 (puerto 5005): recibe cada fruta y lleva los contadores del dashboard.
    Además, abriendo http://127.0.0.1:5005/resumen en el navegador se ven los contadores.

Sirve también como EJEMPLO para los otros grupos: así debe recibir sus datos
una estación (POST con JSON en la ruta /fruta).

Uso, en una terminal aparte:
    python3 simulador_estaciones.py
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Posición del servo para cada calibre (solo para mostrar)
SERVO = {"chico": "izquierda", "mediano": "centro", "grande": "derecha", "revision": "sin mover"}
conteo = {"total": 0, "chico": 0, "mediano": 0, "grande": 0, "revision": 0}


class Estacion4(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        datos = json.loads(self.rfile.read(largo))
        print(f"[Estación 4] fruta {datos['id']}: {datos['calibre']:8s} -> servo: "
              f"{SERVO.get(datos['calibre'], '?')}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):   # no llenar la terminal con cada petición
        pass


class Estacion5(BaseHTTPRequestHandler):
    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        datos = json.loads(self.rfile.read(largo))
        conteo["total"] += 1
        conteo[datos["calibre"]] = conteo.get(datos["calibre"], 0) + 1
        print(f"[Estación 5] dashboard: {conteo}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def do_GET(self):                # http://127.0.0.1:5005/resumen
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(conteo).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    estacion4 = HTTPServer(("0.0.0.0", 5004), Estacion4)
    estacion5 = HTTPServer(("0.0.0.0", 5005), Estacion5)
    threading.Thread(target=estacion4.serve_forever, daemon=True).start()
    print("Estación 4 simulada en el puerto 5004  (POST /fruta)")
    print("Estación 5 simulada en el puerto 5005  (POST /fruta, GET /resumen)")
    print("Esperando frutas... (Ctrl+C para salir)")
    try:
        estacion5.serve_forever()
    except KeyboardInterrupt:
        print("\nSimulador detenido")
