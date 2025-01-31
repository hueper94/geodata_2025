# Automatisiertes Datenmanagement-System

Ein intelligentes System zur automatischen Verwaltung, Analyse und Sicherung von Daten und Code.

## Funktionen

### 1. Datenanalyse
- Automatische Erkennung und Analyse von Dateien
- Unterstützung für Geodaten (GeoJSON, Shapefile)
- Code-Analyse (Python, Shell-Skripte)
- Qualitätsmetriken und Optimierungsvorschläge

### 2. Automatische Organisation
- Intelligente Sortierung in logische Verzeichnisstruktur
- Behandlung von beschädigten Dateien
- Versionskontrolle mit Git
- Cloud-Backup (Nextcloud-Integration)

### 3. Berichterstattung
- Detaillierte Analyseberichte
- Fehlerprotokolle
- Code-Qualitätsberichte
- Optimierungsvorschläge

## Installation

1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

2. Cloud-Konfiguration (optional):
   - Nextcloud-URL
   - Benutzername
   - Passwort
   in `auto_organizer.py` anpassen

## Verwendung

### Automatischer Modus
```bash
python auto_organizer.py
```
Das System läuft dann kontinuierlich und:
- Überwacht Änderungen im Dateisystem
- Führt tägliche Analysen durch
- Erstellt wöchentliche Backups
- Macht stündliche Git-Commits

### Manueller Modus
Sie können das System auch manuell starten, um eine sofortige Analyse durchzuführen.

## Verzeichnisstruktur

- `/src/` - Code-Dateien
- `/data/raw/` - Rohdaten
- `/data/processed/` - Verarbeitete Daten
- `/data/corrupted/` - Beschädigte Dateien
- `/logs/` - Protokolle
- `/backups/` - Backup-Archive

## Fehlerbehandlung

Das System protokolliert alle Aktivitäten in:
- `logs/auto_organizer.log`
- `report.txt` (Analysebericht)

## Lizenz

MIT License 