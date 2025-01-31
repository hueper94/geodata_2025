#!/bin/bash

# Verzeichnispfade
WORKSPACE_DIR="/media/sven/L_SSD_LINUX/Folder_1"
VENV_DIR="$WORKSPACE_DIR/env"
API_FILE="$WORKSPACE_DIR/src/backend/api.py"
PID_FILE="/tmp/geodata_website.pid"
LOG_FILE="$WORKSPACE_DIR/logs/website.log"

# Farben für die Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funktion zum Erstellen des Log-Verzeichnisses
create_log_dir() {
    mkdir -p "$WORKSPACE_DIR/logs"
}

# Funktion zum Aktivieren der virtuellen Umgebung
activate_venv() {
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    else
        echo -e "${RED}Fehler: Virtuelle Umgebung nicht gefunden${NC}"
        exit 1
    fi
}

# Funktion zum Überprüfen, ob der Server läuft
is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Funktion zum Starten des Servers
start_server() {
    if is_running; then
        echo -e "${YELLOW}Server läuft bereits (PID: $(cat $PID_FILE))${NC}"
    else
        echo -e "${GREEN}Starte Server...${NC}"
        create_log_dir
        cd "$WORKSPACE_DIR"
        activate_venv
        
        # Server im Hintergrund starten
        python "$API_FILE" > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        
        # Warte kurz, damit der Server Zeit hat zu starten
        sleep 2
        
        echo -e "${GREEN}Server gestartet mit PID: $(cat $PID_FILE)${NC}"
        echo -e "${GREEN}Logs werden geschrieben nach: $LOG_FILE${NC}"
        echo -e "${GREEN}Website ist erreichbar unter: http://localhost:5001${NC}"
        echo -e "${YELLOW}Server-Logs werden angezeigt (CTRL+C zum Beenden):${NC}\n"
        
        # Logs automatisch anzeigen
        tail -f "$LOG_FILE"
    fi
}

# Funktion zum Stoppen des Servers
stop_server() {
    if is_running; then
        echo -e "${YELLOW}Stoppe Server...${NC}"
        pid=$(cat "$PID_FILE")
        kill "$pid"
        rm -f "$PID_FILE"
        echo -e "${GREEN}Server gestoppt${NC}"
    else
        echo -e "${RED}Server läuft nicht${NC}"
    fi
}

# Funktion zum Neustarten des Servers
restart_server() {
    echo -e "${YELLOW}Starte Server neu...${NC}"
    stop_server
    sleep 2
    start_server
}

# Funktion zum Anzeigen des Server-Status
show_status() {
    if is_running; then
        echo -e "${GREEN}Server läuft (PID: $(cat $PID_FILE))${NC}"
        echo -e "${GREEN}Log-Datei: $LOG_FILE${NC}"
        echo -e "${GREEN}Website: http://localhost:5001${NC}"
    else
        echo -e "${RED}Server ist gestoppt${NC}"
    fi
}

# Funktion zum Anzeigen der Logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}Server-Logs werden angezeigt (CTRL+C zum Beenden):${NC}\n"
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}Keine Log-Datei gefunden${NC}"
    fi
}

# Hilfe-Funktion
show_help() {
    echo "Verwendung: $0 {start|stop|restart|status|logs|help}"
    echo "  start   - Startet den Server und zeigt die Logs an"
    echo "  stop    - Stoppt den Server"
    echo "  restart - Startet den Server neu"
    echo "  status  - Zeigt den Server-Status"
    echo "  logs    - Zeigt die Server-Logs"
    echo "  help    - Zeigt diese Hilfe"
}

# Hauptlogik
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help)
        show_help
        ;;
    *)
        echo -e "${RED}Unbekannter Befehl${NC}"
        show_help
        exit 1
        ;;
esac

exit 0 