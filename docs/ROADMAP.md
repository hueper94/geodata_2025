# Projekt Roadmap und Dokumentation

## Aktuelle Projektstruktur
```
.
├── app.py                # Hauptanwendung
├── config/              # Konfigurationsdateien
│   ├── config.json      # OpenAI API-Key
│   └── config.env       # Umgebungsvariablen
├── database/            # Datenbank-Dateien
│   ├── migrations/      # Datenbankmigrationen
│   └── data_lexicon.db  # SQLite Datenbank
├── scripts/             # Hilfsskripte
│   ├── server_control.py
│   └── start_website.sh
├── utils/              # Hilfsfunktionen
├── prompts/            # KI-Prompts
├── templates/          # HTML-Templates
├── static/             # Statische Dateien
│   ├── js/
│   │   ├── main.js
│   │   └── core_functions.js
├── docs/              # Dokumentation
├── logs/              # Logdateien
├── data/              # Hauptdaten
├── wfs_data/          # WFS-spezifische Daten
├── downloads/         # Heruntergeladene Dateien
└── temp_downloads/    # Temporäre Downloads
```

## Implementierte Features (30.01.2024)

1. Verzeichnisstruktur optimiert:
   - Konfigurationsdateien in `config/` zentralisiert
   - Datenbank-Dateien in `database/` organisiert
   - Skripte in `scripts/` zusammengefasst
   - Temporäre Dateien und Caches in `.gitignore` aufgenommen

2. OpenAI Integration:
   - Helper-Klasse für OpenAI-Anfragen implementiert
   - Konfiguration über `config.json`
   - Prompt-Templates in separaten JSON-Dateien
   - Layer-Namen-Bereinigung mit KI
   - Fehlerbehandlung und Logging implementiert

3. Routen-System:
   - Hauptseite (`/`)
   - Datenlexikon (`/data_lexicon`)
   - WFS/WMS Explorer (`/wfs_wms_explorer`)
   - API-Endpunkte für Layer-Verwaltung

## Aktuelle Probleme (30.01.2024)

1. Konfigurationsprobleme:
   - `config.json` fehlt oder ist nicht im richtigen Verzeichnis
   - OpenAI API-Key nicht korrekt konfiguriert
   - Umgebungsvariablen müssen überprüft werden

2. Template-Fehler:
   - `overview.html` Template fehlt
   - Template-Struktur muss überarbeitet werden

3. Server-Probleme:
   - Port 5001 möglicherweise bereits belegt
   - Server-Neustart-Mechanismus verbessern

4. Deprecated Warnungen:
   - LangChain Import veraltet, Umstellung auf `langchain-community` erforderlich

## Geplante Erweiterungen

### 1. Datenlexikon Erweiterungen
- [ ] Speicherung aller WFS-Layer-Namen (nicht nur ausgewählte)
- [ ] Separates Lexikon für alle Attributwerte
- [ ] Erweiterte Suchfunktion für Attributwerte
- [ ] Filter- und Sortiermöglichkeiten
- [ ] Volltextsuche über alle Informationen

### 2. Attribut-Lexikon Features
- [ ] Automatische Erfassung aller Attributwerte
- [ ] Kategorisierung der Attribute
- [ ] Verknüpfung mit Layer-Informationen
- [ ] Statistiken über Attributwerte
- [ ] Export-Funktion für Attributdaten

### 3. Suchfunktionen
- [ ] Implementierung einer erweiterten Suchfunktion
- [ ] Filter nach Attributtypen
- [ ] Filter nach Wertebereichen
- [ ] Fuzzy-Suche für ähnliche Begriffe
- [ ] Mehrsprachige Suche

### 4. UI/UX Verbesserungen
- [ ] Responsive Design optimieren
- [ ] Benutzerfreundliche Filtermöglichkeiten
- [ ] Verbesserte Darstellung der Suchergebnisse
- [ ] Exportmöglichkeiten für gefundene Daten
- [ ] Fortschrittsanzeige bei Datenladung

### 5. Technische Optimierungen
- [ ] Caching-System für WFS-Anfragen
- [ ] Optimierung der Datenbankstruktur
- [ ] Verbesserung der Fehlerbehandlung
- [ ] Performance-Optimierung bei großen Datenmengen
- [ ] API-Dokumentation erstellen

## Nächste Schritte

1. Konfiguration korrigieren:
   - `config.json` im richtigen Verzeichnis erstellen
   - OpenAI API-Key korrekt einrichten
   - Umgebungsvariablen dokumentieren

2. Template-System:
   - Fehlende Templates erstellen
   - Template-Vererbung implementieren
   - Einheitliches Layout entwickeln

3. Server-Stabilität:
   - Port-Konflikte beheben
   - Prozess-Management verbessern
   - Logging erweitern

4. Dependency Updates:
   - LangChain auf neueste Version aktualisieren
   - Abhängigkeiten in `requirements.txt` aktualisieren
   - Deprecated Warnungen beheben

5. Datenlexikon erweitern:
   - Datenbankschema anpassen
   - API-Endpunkte erweitern
   - UI für neue Funktionen erstellen

## Offene Punkte
- Performance bei großen Datenmengen
- Speicheroptimierung für Attributwerte
- Backup-Strategie für Datenbank
- Mehrsprachigkeit
- API-Dokumentation 