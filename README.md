# WFS/WMS Explorer mit Datenlexikon

Ein Tool zur Erkundung und Verwaltung von WFS/WMS-Diensten mit integriertem Datenlexikon und KI-gestützter Namensbereinigung.

## Features

- WFS/WMS Service Explorer
- Datenlexikon für Layer-Namen und Attribute
- KI-gestützte Namensbereinigung
- Erweiterte Suchfunktionen
- Attribut-basierte Filterung

## Installation

1. Python-Umgebung einrichten:
```bash
python -m venv env
source env/bin/activate  # Unter Linux/Mac
env\Scripts\activate     # Unter Windows
```

2. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

3. Konfiguration:
- Kopiere `config.env.example` nach `config/config.env`
- Erstelle `config/config.json` mit OpenAI API-Key

4. Datenbank initialisieren:
```bash
flask db upgrade
```

5. Server starten:
```bash
python app.py
```

## Entwicklung

- Projekt-Roadmap: Siehe `docs/ROADMAP.md`
- Coding-Standards: PEP 8
- Tests: pytest
- Dokumentation: Sphinx

## Lizenz

MIT License - Siehe LICENSE Datei

## Beiträge

Beiträge sind willkommen! Bitte beachten Sie unsere Contribution Guidelines. 