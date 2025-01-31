from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import json
import logging
from ..services.chatgpt_service import ChatGPTService
from ..services.layer_service import LayerService
from ..services.qgis_service import QgisService

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lade den API-Schlüssel aus der JSON-Datei
def lade_api_schluessel(pfad="api.json"):
    try:
        with open(pfad, "r") as file:
            data = json.load(file)
            return data["api_key"]
    except FileNotFoundError:
        logger.error("Die Datei api.json wurde nicht gefunden.")
    except KeyError:
        logger.error("Der Schlüssel 'api_key' ist nicht in der Datei api.json enthalten.")
    except json.JSONDecodeError:
        logger.error("Fehler beim Einlesen der JSON-Datei.")
    return None

# API-Schlüssel aus der Datei laden
api_key = lade_api_schluessel()
if not api_key:
    logger.error("API-Schlüssel konnte nicht geladen werden.")
    exit(1)

# Services initialisieren
chatgpt_service = ChatGPTService(api_key)
layer_service = LayerService()
qgis_service = QgisService()  # Singleton, wird nur einmal initialisiert

# Flask App initialisieren
app = Flask(__name__, template_folder='../../templates')
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/wfs_wms_explorer')
def explorer():
    return render_template('wfs_wms_explorer.html')

@app.route('/get_layers', methods=['POST'])
def get_layers():
    """Ruft die verfügbaren Layer von einem WFS-Dienst ab"""
    wfs_url = request.form.get('wfs_url')
    if not wfs_url:
        return jsonify({'status': 'error', 'message': 'Keine WFS-URL angegeben'})

    try:
        result = layer_service.get_layers(wfs_url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Layer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Abrufen der Layer: {str(e)}'
        })

@app.route('/api/clean-layer-names', methods=['POST'])
def clean_layer_names():
    """Säubert Layer-Namen mit Hilfe von ChatGPT"""
    try:
        data = request.json
        if not data or 'layers' not in data:
            return jsonify({'status': 'error', 'message': 'Keine Layer zum Säubern angegeben'})

        layers = data['layers']
        custom_prompt = data.get('prompt')
        
        try:
            cleaned_data = chatgpt_service.clean_layer_names(layers, custom_prompt)
            return jsonify(cleaned_data)
        except Exception as e:
            logger.error(f"Fehler bei der ChatGPT-Anfrage: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Fehler bei der KI-Verarbeitung: {str(e)}'
            })

    except Exception as e:
        logger.error(f"Fehler beim Säubern der Layer-Namen: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Säubern der Layer-Namen: {str(e)}'
        })
