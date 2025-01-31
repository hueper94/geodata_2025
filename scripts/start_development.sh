#!/bin/bash

# Lade Umgebungsvariablen
set -a
source .env.development
set +a

echo "=== Starte Entwicklungsserver ==="
echo "Port: $PORT"
echo "Datenbank: $DATABASE_PATH"
echo "Debug-Modus: $DEBUG"

# Starte den Entwicklungsserver
python app.py 