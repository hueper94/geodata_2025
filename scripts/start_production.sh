#!/bin/bash

# Lade Umgebungsvariablen
set -a
source .env.production
set +a

echo "=== Starte Produktionsserver ==="
echo "Port: $PORT"
echo "Datenbank: $DATABASE_PATH"
echo "Debug-Modus: $DEBUG"

# Starte den Produktionsserver
python app.py 