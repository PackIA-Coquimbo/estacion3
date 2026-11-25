#!/bin/bash
# Inicia la Estación 3 en modo cinta (para usar en la Raspberry Pi).
# Se puede ejecutar a mano (./iniciar_estacion3.sh) o al encender la Raspberry.
cd "$(dirname "$0")"
source venv/bin/activate
python3 estacion3_cinta.py >> registro_ejecucion.log 2>&1
