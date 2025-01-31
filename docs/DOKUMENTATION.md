# WFS Explorer mit KI-Integration - Dokumentation

## Inhaltsverzeichnis
1. [Projektübersicht](#projektübersicht)
2. [Codestruktur](#codestruktur)
3. [Frontend-Implementierung](#frontend-implementierung)
4. [Backend-Implementierung](#backend-implementierung)
5. [Templates](#templates)
6. [Funktionsweise](#funktionsweise)
7. [Besonderheiten](#besonderheiten)

## Projektübersicht
Der WFS Explorer ist eine Webanwendung zur Verwaltung und Anzeige von WFS-Layern mit integrierter KI-Funktionalität zur Bereinigung von Layer-Namen.

## Codestruktur

### 1. Frontend (JavaScript)

#### a) `static/js/main.js`
```javascript
// Hauptdatei für die Initialisierung
import { wfsService } from './wfs_service.js';
import { aiCleanerService } from './ai_cleaner_service.js';

document.addEventListener('DOMContentLoaded', () => {
    console.log('Initialisiere WFS Explorer...');
});
```
**Funktionalität:**
- Zentrale Einstiegsdatei
- Importiert und initialisiert die Services
- Minimalistischer Aufbau für bessere Wartbarkeit

#### b) `static/js/wfs_service.js`
```javascript
class WFSService {
    constructor() {...}
    log(message) {...}
    showError(message) {...}
    showSuccess(message) {...}
    initializeEventListeners() {...}
    async loadLayers() {...}
    async displayLayers(data) {...}
}
```
**Funktionalität:**
- Verwaltet WFS-Funktionalität
- Lädt Layer vom WFS-Server
- Zeigt Layer in einer Tabelle an
- Handhabt Benutzerinteraktionen mit Layern
- Implementiert Event-System für Layer-Ladung

#### c) `static/js/ai_cleaner_service.js`
```javascript
class AiCleanerService {
    constructor() {...}
    log(message) {...}
    showError(message) {...}
    showSuccess(message) {...}
    initializeEventListeners() {...}
    addCleanButton() {...}
    getSelectedLayers() {...}
    async cleanSelectedLayers() {...}
    updateLayerNames(cleanedLayers) {...}
}
```
**Funktionalität:**
- Handhabt KI-basierte Layernamen-Bereinigung
- Fügt dynamisch einen "Clean"-Button hinzu
- Kommuniziert mit dem Backend für KI-Verarbeitung
- Aktualisiert die UI mit bereinigten Namen
- Implementiert detaillierte Fehlerbehandlung

#### d) `static/js/utils.js`
```javascript
export function showError(message) {...}
export function showSuccess(message) {...}
export function showLoadingOverlay(show, status = '', details = '') {...}
```
**Funktionalität:**
- Gemeinsam genutzte Hilfsfunktionen
- Einheitliches Benachrichtigungssystem
- Lade-Overlay-Verwaltung
- Konsolenprotokollierung

### 2. Backend (Python)

#### a) `app.py`
```python
from flask import Flask, request, jsonify, render_template
# ... weitere Imports

app = Flask(__name__)
# ... Routen und Funktionen
```
**Funktionalität:**
- Flask-Server-Implementierung
- Definiert alle API-Endpunkte
- Handhabt WFS-Anfragen
- Verarbeitet KI-Anfragen
- Implementiert Fehlerbehandlung und Logging

#### b) `utils/openai_helper.py`
```python
class OpenAIHelper:
    def __init__(self, config_path='config/config.json', prompts_dir='prompts') {...}
    def load_config(self, config_path) {...}
    def clean_layer_names_batch(self, layer_names) {...}
    def clean_layer_name(self, layer_name) {...}
```
**Funktionalität:**
- OpenAI API Integration
- Konfigurationsmanagement
- Batch-Verarbeitung von Layer-Namen
- KI-Prompt-Management
- Fehlerbehandlung für API-Anfragen

### 3. Templates

#### `templates/wfs_wms_explorer.html`
```html
<!DOCTYPE html>
<html lang="de">
    <!-- Struktur und Styling -->
    <!-- Formular für WFS -->
    <!-- Layer-Tabelle -->
    <!-- Modals und Overlays -->
</html>
```
**Funktionalität:**
- Responsive Benutzeroberfläche
- Bootstrap-Integration
- Formular für WFS-URL-Eingabe
- Dynamische Layer-Tabelle
- Benachrichtigungssystem
- Lade-Overlay
- Modal für Layer-Details

## Funktionsweise

### Ablauf einer typischen Benutzerinteraktion:
1. Der Benutzer gibt eine WFS-URL ein
2. Der `WFSService` lädt die Layer
3. Die Layer werden in einer Tabelle angezeigt
4. Der `AiCleanerService` fügt einen Clean-Button hinzu
5. Bei Klick auf den Button werden ausgewählte Layer an die KI gesendet
6. Die bereinigten Namen werden zurückgegeben und angezeigt
7. Alle Aktionen werden durch das Benachrichtigungssystem begleitet

## Besonderheiten

### Technische Merkmale:
- **Modularer Aufbau** für einfache Wartung
- **Ausführliche Fehlerbehandlung** in allen Komponenten
- **Detailliertes Logging** für Debugging
- **Responsive Benutzeroberfläche** mit Bootstrap
- **Asynchrone Verarbeitung** für bessere Performance
- **Einheitliches Styling** durch CSS-Variablen
- **Benutzerfreundliche Rückmeldungen** durch Notifications

### Sicherheitsaspekte:
- Sichere Handhabung von API-Keys
- Validierung von Benutzereingaben
- Fehlertolerante Verarbeitung
- CORS-Schutz
- SSL-Unterstützung

### Wartung und Erweiterung:
- Klare Trennung von Zuständigkeiten
- Gut dokumentierter Code
- Einfache Integration neuer Features
- Testbare Komponenten
- Konfigurierbare Parameter

## API-Endpunkte

### WFS-Endpunkte:
- `GET /wfs_wms_explorer`: Hauptseite
- `POST /get_layers`: Lädt Layer von WFS-Server
- `POST /prepare_download`: Bereitet Layer-Download vor
- `POST /load_selected_layer`: Lädt ausgewählte Layer

### KI-Endpunkte:
- `POST /api/clean-layer-names`: Bereinigt Layer-Namen mit KI

## Konfiguration

### OpenAI-Konfiguration:
```json
{
    "openai_api_key": "Ihr-API-Key"
}
```

### Server-Konfiguration:
- Host: 127.0.0.1
- Port: 5001
- Debug-Modus: Aktiviert

## Fehlerbehandlung

### Frontend:
- Benutzerfreundliche Fehlermeldungen
- Automatische Wiederholungsversuche
- Timeout-Handling
- Ladezustands-Anzeige

### Backend:
- Ausführliches Logging
- HTTP-Statuscode-Handling
- Exception-Handling
- Validierung von Eingaben

## Entwicklung und Tests

### Entwicklungsumgebung:
- Python 3.8+
- Node.js für Frontend-Tools
- Flask für Backend
- Bootstrap 5 für UI

### Tests:
- Unit-Tests für Backend
- Integration-Tests für API
- UI-Tests für Frontend
- Performance-Tests

## Wartung

### Regelmäßige Aufgaben:
- API-Key-Rotation
- Log-Rotation
- Cache-Bereinigung
- Dependency-Updates

### Monitoring:
- Server-Status
- API-Verfügbarkeit
- Fehlerprotokolle
- Performance-Metriken 