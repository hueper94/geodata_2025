from flask import Flask, request, jsonify, render_template, send_file
import os
from config import Config
import json
import geopandas as gpd
from shapely.geometry import shape, mapping
from shapely import make_valid
import requests
from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from urllib.parse import urlencode
from wfs_explorer import WFSExplorer
import logging
import traceback
import sys
import tempfile
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# SQLite Konfiguration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///geodata.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Datenbank initialisieren
db = SQLAlchemy(app)

def setup_database():
    """Initialisiert die SQLite-Datenbank"""
    try:
        if not os.path.exists('geodata.db'):
            with app.app_context():
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS geo_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        geom TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                logger.info("Datenbank erfolgreich initialisiert")
    except Exception as e:
        logger.error(f"Fehler bei der Datenbank-Initialisierung: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_layers', methods=['POST'])
def get_layers():
    wfs_url = request.form.get('wfs_url')
    try:
        explorer = WFSExplorer(wfs_url)
        
        # Layer-Struktur und Metadaten abrufen
        layers = explorer.layer_structure
        
        # Für jeden Layer detaillierte Informationen abrufen
        layer_details = {}
        for namespace, ns_layers in layers.items():
            for layer_name in ns_layers:
                details = explorer.get_layer_details(layer_name)
                if details:
                    layer_details[layer_name] = details
        
        response_data = {
            'status': 'success',
            'layers': layers,
            'layer_details': layer_details,
            'formats': explorer.supported_formats,
            'metadata': explorer.metadata
        }
        
        logger.info(f"Layer erfolgreich geladen: {len(layer_details)} Layer gefunden")
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = f"Fehler beim Laden der Layer: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500

@app.route('/preview_layer', methods=['POST'])
def preview_layer():
    try:
        wfs_url = request.form.get('wfs_url')
        layer_name = request.form.get('layer_name')
        bbox = request.form.get('bbox')
        
        logger.info(f"Preview Layer Anfrage: URL={wfs_url}, Layer={layer_name}, BBOX={bbox}")
        
        explorer = WFSExplorer(wfs_url)
        geojson_data = explorer.get_preview_data(layer_name, bbox)
        
        if not geojson_data:
            return jsonify({
                'status': 'error',
                'message': 'Keine Daten gefunden'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': geojson_data
        })
        
    except Exception as e:
        return handle_error(e, 'preview_layer')

@app.route('/download_data', methods=['GET'])
def download_data():
    try:
        wfs_url = request.args.get('wfs_url')
        layer_name = request.args.get('layer_name')
        output_format = request.args.get('format', 'GEOJSON')
        bbox = request.args.get('bbox')
        
        logger.info(f"Download Anfrage: URL={wfs_url}, Layer={layer_name}, Format={output_format}, BBOX={bbox}")
        
        explorer = WFSExplorer(wfs_url)
        output_file = explorer.download_and_convert(
            layer_name, 
            output_format=output_format,
            bbox=bbox
        )
        
        if not output_file or not os.path.exists(output_file):
            return jsonify({
                'status': 'error',
                'message': 'Fehler beim Erstellen der Datei'
            }), 500
        
        # Bestimme den korrekten MIME-Type
        mime_types = {
            'GEOJSON': 'application/json',
            'SHAPEFILE': 'application/zip',
            'GPKG': 'application/geopackage+sqlite3'
        }
        mime_type = mime_types.get(output_format.upper(), 'application/octet-stream')
        
        return send_file(
            output_file,
            as_attachment=True,
            download_name=f"{layer_name.replace(':', '_')}.{output_format.lower()}",
            mimetype=mime_type
        )
        
    except Exception as e:
        return handle_error(e, 'download_data')

def handle_error(e, endpoint):
    """Zentrale Fehlerbehandlung mit detailliertem Logging"""
    error_msg = f"Fehler in {endpoint}: {str(e)}"
    stack_trace = traceback.format_exc()
    logger.error(f"{error_msg}\n{stack_trace}")
    return jsonify({
        'status': 'error',
        'message': error_msg,
        'details': stack_trace
    }), 500

if __name__ == '__main__':
    # Datenbank initialisieren
    setup_database()
    
    # Flask-App starten
    app.run(debug=True, port=5004, host='127.0.0.1') 