#!/bin/bash
# Inicia la app de la Estación 3 (para la Raspberry Pi o el Mac).
# Se abre en el navegador: http://localhost:8000
cd "$(dirname "$0")"
source venv/bin/activate
python3 app_estacion3.py >> registro_ejecucion.log 2>&1
