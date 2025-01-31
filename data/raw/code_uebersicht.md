# Code-Übersicht des Projekts

## Backend (`src/backend/`)

### `src/backend/api.py`
- Flask-API mit OpenAI-Integration
- Endpunkte:
  - `/api/analyze`: Geodaten-Analyse mit KI
  - `/api/rename`: KI-basierte Dateiumbenennung
  - `/api/test`: API-Test
  - `/api/wfs/download`: WFS-Daten-Download

## Frontend (`src/frontend/`)

### `src/frontend/wfs_explorer.py`
- WFS-Dienst Explorer
- Funktionen für WFS-Verbindung und Datenabfrage

### `src/frontend/wms_explorer.py`
- WMS-Dienst Explorer
- Funktionen für WMS-Layer-Verwaltung

## Utils (`src/utils/`)

### `src/utils/auto_organizer.py`
- Automatische Dateiverwaltung
- Sortierung und Organisation von Geodaten

### `src/utils/config.py`
- Konfigurationsverwaltung
- Systemeinstellungen

### `src/utils/check_wfs.py`
- WFS-Validierung
- Prüfung von WFS-Diensten

### `src/utils/tabel.py`
- Tabellenverarbeitung
- Datentransformation

### `src/utils/test_wms_extraction.py`
- WMS-Tests
- Validierung der WMS-Funktionalität

### `src/utils/start_auto_organizer.sh`
- Startskript für Auto-Organizer
- Automatischer Start des Systems

### `src/utils/cb46901d7ea7_initial_migration.py`
- Datenbank-Migration
- Initiale Datenbankstruktur

## Web-Interface

### `templates/index.html`
- Hauptseite der Web-Anwendung
- Kartenansicht und Steuerelemente

### `static/js/map.js`
- JavaScript für Karteninteraktion
- Layer-Management und Visualisierung

## Konfigurationsdateien

### `data/raw/config.json`
- OpenAI API-Konfiguration
- API-Einstellungen

### `data/raw/requirements.txt`
- Python-Abhängigkeiten
- Benötigte Pakete und Versionen

### `auto_organizer.service`
- Systemd-Service-Definition
- Automatischer Start als Systemdienst

### `auto_organizer.desktop`
- Desktop-Starter
- Autostart-Integration

## Datenbank

### `migrations/env.py`
- Alembic-Migrationsumgebung
- Datenbank-Versionierung

## Dokumentation

### `data/raw/webgis_roadmap.md`
- Projekt-Roadmap
- Entwicklungsplan und Status

### `data/raw/code_uebersicht.md`
- Diese Datei
- Übersicht aller Code-Dateien

## Verzeichnisstruktur

```
src/
├── backend/
│   └── api.py
├── frontend/
│   ├── wfs_explorer.py
│   └── wms_explorer.py
└── utils/
    ├── auto_organizer.py
    ├── config.py
    ├── check_wfs.py
    ├── tabel.py
    ├── test_wms_extraction.py
    ├── start_auto_organizer.sh
    └── cb46901d7ea7_initial_migration.py

templates/
└── index.html

static/
└── js/
    └── map.js

data/
└── raw/
    ├── config.json
    ├── requirements.txt
    ├── webgis_roadmap.md
    └── code_uebersicht.md
``` 