#!/bin/bash

# Farben für die Ausgabe
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Einrichtung der Entwicklungs- und Produktionsumgebung ===${NC}"

# Erstelle Verzeichnisse
echo -e "${GREEN}Erstelle Verzeichnisstruktur...${NC}"
mkdir -p database/development
mkdir -p database/production
mkdir -p logs/development
mkdir -p logs/production

# Kopiere Datenbank-Template wenn vorhanden
if [ -f "database/data_lexicon.db" ]; then
    echo -e "${GREEN}Kopiere bestehende Datenbank für beide Umgebungen...${NC}"
    cp database/data_lexicon.db database/development/development_lexicon.db
    cp database/data_lexicon.db database/production/production_lexicon.db
fi

# Setze Berechtigungen für die Skripte
echo -e "${GREEN}Setze Ausführungsrechte für Skripte...${NC}"
chmod +x scripts/start_development.sh
chmod +x scripts/start_production.sh

echo -e "${GREEN}Erstelle Umgebungsvariablen-Dateien...${NC}"

# Entwicklungsumgebung
cat > .env.development << EOL
FLASK_ENV=development
FLASK_APP=app.py
DATABASE_PATH=database/development/development_lexicon.db
PORT=5002
DEBUG=True
EOL

# Produktionsumgebung
cat > .env.production << EOL
FLASK_ENV=production
FLASK_APP=app.py
DATABASE_PATH=database/production/production_lexicon.db
PORT=5001
DEBUG=False
EOL

echo -e "${BLUE}=== Setup abgeschlossen ===${NC}"
echo -e "${GREEN}Entwicklungsserver starten mit: ./scripts/start_development.sh${NC}"
echo -e "${GREEN}Produktionsserver starten mit: ./scripts/start_production.sh${NC}" 