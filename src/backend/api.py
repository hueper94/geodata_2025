from flask import Flask, jsonify, request, render_template, send_file, Response, stream_with_context
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
import requests
import geopandas as gpd
import tempfile
import logging
import time
from urllib.parse import urljoin, parse_qs, urlparse, quote, unquote
import xml.etree.ElementTree as ET
from owslib.wfs import WebFeatureService
import pandas as pd
from shapely.geometry import shape
import math
import urllib3
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingFeedback
)
from threading import Lock, Thread
from PyQt5.QtCore import QThread
import zipfile
import re
import shutil
import sqlite3
from datetime import datetime
from langchain_community.llms import OpenAI
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Lade Umgebungsvariablen aus config.env
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.env')
load_dotenv(config_path)

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# QGIS Thread für Timer
class QgisThread(QThread):
    def __init__(self):
        super().__init__()
        self.app = None
        
    def run(self):
        self.app = QgsApplication([], False)
        self.app.setPrefixPath('/usr', True)
        self.app.initQgis()
        logger.info("QGIS in separatem Thread initialisiert")
        self.exec_()

# QGIS Umgebungsvariablen setzen
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QGIS_PREFIX_PATH'] = '/usr'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/usr/lib/x86_64-linux-gnu/qt5/plugins'

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# QGIS in separatem Thread starten
logger.info("Starte QGIS-Thread...")
qgis_thread = QgisThread()
qgis_thread.start()
time.sleep(2)  # Warte bis QGIS initialisiert ist

# Projekt initialisieren
project = QgsProject.instance()
logger.info(f"QGIS-Projekt initialisiert - CRS: {project.crs().authid()}")

# Layer-Cache für Status-Tracking
layer_cache = {}
layer_cache_lock = Lock()

class LayerStatus:
    LOADING = 'loading'
    READY = 'ready'
    ERROR = 'error'

app = Flask(__name__, template_folder='../../templates', static_folder='../../static')
CORS(app)

# Verfügbare WFS Versionen
WFS_VERSIONS = ['2.0.0', '1.1.0', '1.0.0']

def test_wfs_version(url, version):
    """
    Testet, ob ein WFS-Dienst mit einer bestimmten Version funktioniert
    """
    try:
        params = {
            'service': 'WFS',
            'version': version,
            'request': 'GetCapabilities'
        }
        response = requests.get(url, params=params, timeout=10, verify=False)
        if response.status_code == 200:
            try:
                root = ET.fromstring(response.content)
                if root.find('.//FeatureType') is not None or root.find('.//{http://www.opengis.net/wfs/2.0}FeatureType') is not None:
                    logger.info(f"WFS Version {version} erfolgreich getestet für {url}")
                    return True
            except ET.ParseError:
                logger.error(f"Ungültige XML-Antwort für Version {version}")
                return False
        logger.warning(f"WFS Version {version} nicht erfolgreich für {url} (Status: {response.status_code})")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Verbindungsfehler beim Testen von WFS Version {version}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Testen von WFS Version {version}: {str(e)}")
        return False

def get_working_wfs_version(url):
    """
    Findet die funktionierende WFS-Version für einen Dienst
    """
    logger.info(f"Teste WFS-Versionen für URL: {url}")
    working_versions = []
    
    for version in WFS_VERSIONS:
        if test_wfs_version(url, version):
            working_versions.append(version)
            logger.info(f"Gefundene funktionierende Version: {version}")
    
    if working_versions:
        return working_versions[0]
    
    logger.error(f"Keine funktionierende WFS-Version gefunden für {url}")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/wfs_wms_explorer')
def explorer():
    return render_template('wfs_wms_explorer.html')

@app.route('/get_layers', methods=['POST'])
def get_layers():
    wfs_url = request.form.get('wfs_url')
    if not wfs_url:
        return jsonify({'status': 'error', 'message': 'Keine WFS-URL angegeben'})
    
    logger.info(f"Versuche WFS-Layer zu laden von: {wfs_url}")
    
    try:
        # GetCapabilities-Anfrage mit SSL-Verifizierung deaktiviert
        params = {
            'service': 'WFS',
            'request': 'GetCapabilities'
        }
        
        response = requests.get(wfs_url, params=params, verify=False, timeout=30)
        if response.status_code != 200:
            logger.error(f"Server-Fehler: Status {response.status_code}")
            return jsonify({
                'status': 'error',
                'message': f'Server antwortet nicht (Status: {response.status_code})'
            })

        # Parse XML mit besserer Fehlerbehandlung
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error(f"XML-Parsing-Fehler: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Ungültige Server-Antwort: Kein gültiges XML'
            })

        # Finde WFS Version
        version = root.get('version')
        if not version:
            # Versuche alternative Versionen
            for v in WFS_VERSIONS:
                params['version'] = v
                response = requests.get(wfs_url, params=params, verify=False)
                if response.status_code == 200:
                    version = v
                    root = ET.fromstring(response.content)
                    break
        
        if not version:
            return jsonify({
                'status': 'error',
                'message': 'Keine kompatible WFS-Version gefunden'
            })

        # Namespace-Handling
        namespaces = {
            'wfs': 'http://www.opengis.net/wfs/2.0',
            'wfs1': 'http://www.opengis.net/wfs',
            'ows': 'http://www.opengis.net/ows/1.1',
            'ows2': 'http://www.opengis.net/ows'
        }
        
        layers = {}
        feature_types = []

        # Suche FeatureTypes
        for xpath in [
            './/wfs:FeatureType',
            './/wfs1:FeatureType',
            './/FeatureType'
        ]:
            feature_types = root.findall(xpath, namespaces)
            if feature_types:
                break

        if not feature_types:
            return jsonify({
                'status': 'error',
                'message': 'Keine Layer im WFS-Dienst gefunden'
            })

        # Layer-Informationen sammeln
        for feature_type in feature_types:
            name = None
            for name_path in ['Name', 'wfs:Name', 'wfs1:Name']:
                name_elem = feature_type.find(name_path, namespaces)
                if name_elem is not None:
                    name = name_elem.text
                    break

            if name is None:
                continue

            title = None
            for title_path in ['Title', 'wfs:Title', 'wfs1:Title']:
                title_elem = feature_type.find(title_path, namespaces)
                if title_elem is not None:
                    title = title_elem.text
                    break

            title = title or name
            
            # ATKIS Layer erkennen und verarbeiten
            if name.startswith('ax_'):
                title = process_atkis_layer(name, title)

            namespace = name.split(':')[0] if ':' in name else 'default'
            layer_name = name.split(':')[1] if ':' in name else name

            if namespace not in layers:
                layers[namespace] = {}

            layers[namespace][layer_name] = {
                'title': title,
                'name': name
            }

        return jsonify({
            'status': 'success',
            'version': version,
            'layers': layers,
            'wfs_url': wfs_url,
            'message': f'WFS Version {version} erfolgreich geladen'
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Verbindungsfehler: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Verbindungsfehler zum WFS-Server'
        })
    except ET.ParseError as e:
        logger.error(f"XML-Parsing-Fehler: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Ungültige Server-Antwort'
        })
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Laden der Layer: {str(e)}'
        })

def download_wfs_with_paging(wfs_url, layer_name, version, output_format='GeoJSON'):
    """
    Lädt WFS-Daten seitenweise herunter und konvertiert sie in das gewünschte Format
    """
    try:
        logger.info(f"Starte Download für Layer {layer_name} im Format {output_format}")
        
        # WFS-Verbindung mit Timeout und ohne SSL-Verifizierung
        wfs = WebFeatureService(url=wfs_url, version=version, timeout=30, verify=False)
        
        # Bestimme das richtige Ausgabeformat für die WFS-Anfrage
        if version == '2.0.0':
            output_formats = wfs.getOperationByName('GetFeature').parameters['outputFormat']['values']
            if 'application/json' in output_formats:
                wfs_output = 'application/json'
            elif 'GML3' in output_formats:
                wfs_output = 'GML3'
            elif 'GML2' in output_formats:
                wfs_output = 'GML2'
            else:
                wfs_output = output_formats[0]
        else:
            wfs_output = 'GML2'
        
        logger.info(f"Verwende WFS-Ausgabeformat: {wfs_output}")
        
        # Features abrufen ohne Limit
        response = wfs.getfeature(
            typename=layer_name,
            outputFormat=wfs_output
        )
        
        if not response:
            raise Exception("Keine Antwort vom WFS-Server")
        
        # Temporäre Datei für die GML/XML-Antwort
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.gml', delete=False) as tmp_gml:
            content = response.read()
            if not content:
                raise Exception("Leere Antwort vom WFS-Server")
                
            tmp_gml.write(content)
            tmp_gml.flush()
            
            logger.info(f"GML-Datei erstellt: {os.path.getsize(tmp_gml.name)} Bytes")
            
            # GML in GeoDataFrame konvertieren
            try:
                gdf = gpd.read_file(tmp_gml.name)
            except Exception as e:
                raise Exception(f"Fehler beim Lesen der GML-Datei: {str(e)}")
            
            # Temporäre GML-Datei löschen
            os.unlink(tmp_gml.name)
            
            if gdf.empty:
                raise Exception("Keine Features im Layer gefunden")
            
            logger.info(f"Anzahl Features geladen: {len(gdf)}")
            
            # CRS auf EPSG:4326 (WGS84) setzen falls nötig
            if gdf.crs is None:
                gdf.crs = 'EPSG:4326'
            elif gdf.crs != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
            
            # In gewünschtes Format exportieren
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format.lower()}') as tmp:
                if output_format.upper() == 'GEOJSON':
                    gdf.to_file(tmp.name, driver='GeoJSON')
                elif output_format.upper() == 'GPKG':
                    gdf.to_file(tmp.name, driver='GPKG')
                elif output_format.upper() == 'SHAPEFILE':
                    gdf.to_file(tmp.name, driver='ESRI Shapefile')
                else:
                    raise ValueError(f'Nicht unterstütztes Format: {output_format}')
                
                file_size = os.path.getsize(tmp.name)
                logger.info(f"Exportierte Datei: {file_size} Bytes")
                
                if file_size == 0:
                    raise Exception("Exportierte Datei ist leer")
                
                return tmp.name
                
    except Exception as e:
        logger.error(f"Fehler beim Download der WFS-Daten: {str(e)}")
        raise

def add_to_layer_cache(cache_id, layer):
    """Thread-sicher Layer zum Cache hinzufügen"""
    with layer_cache_lock:
        layer_cache[cache_id] = {
            'layer': layer,
            'status': LayerStatus.LOADING,
            'feature_count': 0,
            'error_message': None,
            'created_at': time.time(),
            'last_check': time.time(),
            'last_feature_count': 0
        }

def remove_from_layer_cache(cache_id):
    """Thread-sicher Layer aus Cache entfernen"""
    with layer_cache_lock:
        if cache_id in layer_cache:
            layer_info = layer_cache[cache_id]
            if layer_info['layer']:
                project.removeMapLayer(layer_info['layer'].id())
            del layer_cache[cache_id]

def clean_layer_cache():
    """Alte Layer aus dem Cache entfernen"""
    with layer_cache_lock:
        current_time = time.time()
        expired_ids = [
            cache_id for cache_id, info in layer_cache.items()
            if current_time - info['created_at'] > 3600  # 1 Stunde Timeout
        ]
        for cache_id in expired_ids:
            remove_from_layer_cache(cache_id)

def check_layer_status(layer_info):
    """Prüft den Status eines Layers und aktualisiert die Cache-Informationen"""
    try:
        layer = layer_info['layer']
        current_time = time.time()
        
        # Prüfe grundlegende Layer-Gültigkeit
        if not layer or not layer.isValid():
            layer_info['status'] = LayerStatus.ERROR
            layer_info['error_message'] = 'Layer ist nicht gültig'
            return
        
        # Prüfe Provider-Status
        provider = layer.dataProvider()
        if not provider or not provider.isValid():
            layer_info['status'] = LayerStatus.ERROR
            layer_info['error_message'] = 'Datenprovider ist nicht verfügbar'
            return
            
        # Hole aktuelle Feature-Anzahl
        try:
            current_count = layer.featureCount()
            layer_info['feature_count'] = current_count
            logger.info(f"Aktuelle Feature-Anzahl: {current_count}")
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Feature-Anzahl: {str(e)}")
            current_count = 0
        
        # Prüfe ob der Layer noch lädt
        is_loading = layer.isLoading()
        logger.info(f"Layer-Status - Loading: {is_loading}, Features: {current_count}")
        
        if is_loading:
            layer_info['status'] = LayerStatus.LOADING
            return
            
        # Prüfe ob sich die Feature-Anzahl in den letzten 0.5 Sekunden geändert hat
        if current_time - layer_info['last_check'] > 0.5:  # Auf 500ms reduziert
            if current_count == layer_info['last_feature_count']:
                # Keine Änderung seit der letzten Prüfung
                if current_count > 0:
                    # Layer ist fertig geladen
                    layer_info['status'] = LayerStatus.READY
                    logger.info(f"Layer fertig geladen mit {current_count} Features")
                else:
                    # Prüfe ob der Layer eine gültige Ausdehnung hat
                    extent = layer.extent()
                    if extent.isNull():
                        # Warte noch maximal 2 Sekunden bevor wir einen Fehler melden
                        if current_time - layer_info['created_at'] > 2:
                            layer_info['status'] = LayerStatus.ERROR
                            layer_info['error_message'] = 'Keine Features gefunden'
                            logger.error("Layer hat keine Features und keine gültige Ausdehnung")
                    else:
                        # Layer hat eine Ausdehnung aber keine Features (könnte normal sein)
                        layer_info['status'] = LayerStatus.READY
                        logger.info("Layer hat keine Features aber eine gültige Ausdehnung")
            else:
                # Features werden noch geladen
                logger.info(f"Features werden geladen: {layer_info['last_feature_count']} -> {current_count}")
            
            layer_info['last_feature_count'] = current_count
            layer_info['last_check'] = current_time
            
    except Exception as e:
        logger.error(f"Fehler beim Prüfen des Layer-Status: {str(e)}", exc_info=True)
        layer_info['status'] = LayerStatus.ERROR
        layer_info['error_message'] = str(e)

# Datenlexikon Datenbank initialisieren
def init_data_lexicon():
    db_path = os.path.join(os.getcwd(), 'data_lexicon.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS wfs_layers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT, 
                  title TEXT, 
                  translated_title TEXT,
                  type TEXT, 
                  source_url TEXT,
                  attributes TEXT,
                  discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def add_to_lexicon(layer_name, layer_title, layer_type, source_url, attributes=None):
    """Fügt einen Layer zum Lexikon hinzu"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''INSERT INTO wfs_layers 
                  (name, title, type, source_url, attributes) 
                  VALUES (?, ?, ?, ?, ?)
                  ON CONFLICT(name) DO UPDATE SET
                  title=excluded.title,
                  type=excluded.type,
                  source_url=excluded.source_url,
                  attributes=excluded.attributes''',
                  (layer_name, layer_title, layer_type, source_url, 
                   json.dumps(attributes) if attributes else None))
        
        conn.commit()
        logger.info(f"Layer {layer_name} zum Lexikon hinzugefügt")
        
    except Exception as e:
        logger.error(f"Fehler beim Hinzufügen zum Lexikon: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/delete_lexicon_entry', methods=['POST'])
def delete_lexicon_entry():
    """Löscht einen Eintrag aus dem Datenlexikon"""
    try:
        entry_id = request.form.get('id')
        if not entry_id:
            return jsonify({'status': 'error', 'message': 'Keine ID angegeben'})
            
        db_path = os.path.join(os.getcwd(), 'data_lexicon.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('DELETE FROM wfs_layers WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Eintrag erfolgreich gelöscht'
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Löschen des Lexikon-Eintrags: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/data_lexicon')
def show_data_lexicon():
    """Zeigt das Daten-Lexikon an"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''SELECT name, title, translated_title, type, source_url, attributes, discovery_date
                  FROM wfs_layers ORDER BY discovery_date DESC''')
        layers = c.fetchall()
        
        return render_template('data_lexicon.html', layers=layers)
    except Exception as e:
        logger.error(f"Fehler beim Anzeigen des Lexikons: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        if 'conn' in locals():
            conn.close()

# Modifiziere die prepare_download Funktion
@app.route('/prepare_download', methods=['POST'])
def prepare_download():
    """Lädt den Layer in QGIS und exportiert ihn direkt"""
    layer = None
    tmp_dir = None
    try:
        wfs_url = request.form.get('wfs_url')
        layer_name = request.form.get('layer_name')
        layer_title = request.form.get('layer_title', layer_name)
        output_format = request.form.get('format', 'GEOJSON').upper()

        if not wfs_url or not layer_name:
            return jsonify({'status': 'error', 'message': 'URL oder Layer-Name fehlt'}), 400
        
        logger.info(f"Starte Download für Layer: {layer_title} im Format {output_format}")
        
        # WFS Version automatisch erkennen
        version = get_working_wfs_version(wfs_url)
        if not version:
            return jsonify({'status': 'error', 'message': 'Keine kompatible WFS-Version gefunden'}), 400
        
        # WFS Layer mit QGIS laden
        uri = QgsDataSourceUri()
        uri.setParam('url', wfs_url)
        uri.setParam('typename', layer_name)
        uri.setParam('version', version)
        uri.setParam('srsname', 'EPSG:4326')
        uri.setParam('pagingEnabled', 'false')
        
        logger.info(f"WFS URI: {uri.uri()}")
        
        # Layer erstellen
        layer = QgsVectorLayer(uri.uri(), layer_name, 'WFS')
        
        if not layer.isValid():
            error = layer.error()
            logger.error(f"Layer konnte nicht geladen werden - Fehler: {error.summary()}")
            return jsonify({
                'status': 'error',
                'message': f'Layer konnte nicht geladen werden: {error.summary()}'
            }), 400

        # Warte bis Features geladen sind
        start_time = time.time()
        last_count = 0
        while True:
            current_count = layer.featureCount()
            if current_count > 0 and current_count == last_count:
                break
            if time.time() - start_time > 30:
                return jsonify({
                    'status': 'error',
                    'message': 'Zeitüberschreitung beim Laden des Layers'
                }), 408
            last_count = current_count
            time.sleep(0.5)

        logger.info(f"Layer geladen mit {current_count} Features")

        # Puffer mit 0 Metern anwenden
        buffered_layer = QgsVectorLayer(f"MultiPolygon?crs=EPSG:4326", "buffered", "memory")
        buffered_layer.startEditing()
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            # Puffer mit 0 Metern anwenden (bereinigt die Geometrie)
            buffered_geom = geom.buffer(0, 5)  # 5 Segmente für Rundungen
            feat = feature
            feat.setGeometry(buffered_geom)
            buffered_layer.addFeature(feat)
        
        buffered_layer.commitChanges()

        # Format-spezifische Konfiguration
        format_config = {
            'SHAPEFILE': {
                'driver': 'ESRI Shapefile',
                'ext': '.zip',
                'mime': 'application/zip'
            },
            'GEOJSON': {
                'driver': 'GeoJSON',
                'ext': '.geojson',
                'mime': 'application/geo+json'
            },
            'GPKG': {
                'driver': 'GPKG',
                'ext': '.gpkg',
                'mime': 'application/geopackage+sqlite3'
            }
        }

        if output_format not in format_config:
            return jsonify({'status': 'error', 'message': 'Nicht unterstütztes Format'}), 400

        config = format_config[output_format]
        
        # Bereinige den Layertitel für die Verwendung als Dateiname
        safe_title = re.sub(r'[^a-z0-9äöüß\s-]', '_', layer_title.lower()).strip()
        
        # Export des gepufferten Layers
        if output_format == 'SHAPEFILE':
            tmp_dir = tempfile.mkdtemp()
            output_path = os.path.join(tmp_dir, f"{safe_title}.shp")
            error = QgsVectorFileWriter.writeAsVectorFormat(
                buffered_layer,
                output_path,
                'UTF-8',
                buffered_layer.crs(),
                config['driver']
            )

            if isinstance(error, tuple):
                error = error[0]

            if error != QgsVectorFileWriter.NoError:
                return jsonify({'status': 'error', 'message': 'Fehler beim Export der Daten'}), 500

            # ZIP-Archiv erstellen
            zip_path = os.path.join(tmp_dir, f"{safe_title}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                    file_path = output_path.replace('.shp', ext)
                    if os.path.exists(file_path):
                        zipf.write(file_path, os.path.basename(file_path))
            output_path = zip_path
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=config['ext']) as tmp:
                output_path = tmp.name
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    buffered_layer,
                    output_path,
                    'UTF-8',
                    buffered_layer.crs(),
                    config['driver']
                )

        # Zum Lexikon hinzufügen
        add_to_lexicon(layer_name, layer_title, 'WFS', wfs_url)

        # Datei senden
        try:
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"{safe_title}{config['ext']}",
                mimetype=config['mime']
            )
        except Exception as e:
            logger.error(f"Fehler beim Senden der Datei: {str(e)}")
            return jsonify({'status': 'error', 'message': 'Fehler beim Senden der Datei'}), 500

    except Exception as e:
        logger.error(f"Fehler beim Download: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
    finally:
        if layer:
            QgsProject.instance().removeMapLayer(layer.id())
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except Exception as e:
                logger.error(f"Fehler beim Aufräumen des temporären Verzeichnisses: {str(e)}")
        if 'output_path' in locals() and os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except Exception as e:
                logger.error(f"Fehler beim Löschen der temporären Datei: {str(e)}")

# Initialisiere das Datenlexikon beim Start
init_data_lexicon()

@app.route('/check_status/<cache_id>')
def check_status(cache_id):
    """Prüft den Ladestatus eines Layers"""
    try:
        # Cache-ID dekodieren
        decoded_cache_id = unquote(cache_id)
        logger.info(f"Status-Check für Cache-ID: {decoded_cache_id}")
        
        with layer_cache_lock:
            if decoded_cache_id not in layer_cache:
                return jsonify({
                    'status': 'error',
                    'message': 'Layer nicht gefunden'
                })
            
            layer_info = layer_cache[decoded_cache_id]
            check_layer_status(layer_info)
            
            response = {
                'status': layer_info['status'],
                'feature_count': layer_info['feature_count']
            }
            
            if layer_info['status'] == LayerStatus.ERROR:
                response['message'] = layer_info['error_message']
            elif layer_info['status'] == LayerStatus.LOADING:
                response['message'] = f'Layer wird geladen ({layer_info["feature_count"]} Features bisher)'
            else:
                response['message'] = f'Layer fertig geladen ({layer_info["feature_count"]} Features)'
            
            logger.info(f"Layer-Status: {response}")
            return jsonify(response)
            
    except Exception as e:
        logger.error(f"Fehler beim Status-Check: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Status-Check: {str(e)}'
        })

@app.route('/download_data')
def download_data():
    """Exportiert den geladenen Layer in das gewünschte Format"""
    try:
        cache_id = request.args.get('cache_id')
        if not cache_id:
            return jsonify({'status': 'error', 'message': 'Keine Cache-ID angegeben'})
            
        output_format = request.args.get('format', 'GEOJSON').upper()
        
        with layer_cache_lock:
            if cache_id not in layer_cache:
                return jsonify({'status': 'error', 'message': 'Layer nicht gefunden'})
            
            layer_info = layer_cache[cache_id]
            check_layer_status(layer_info)
            
            if layer_info['status'] != LayerStatus.READY:
                return jsonify({
                    'status': 'error',
                    'message': f'Layer ist nicht bereit: {layer_info["error_message"] if "error_message" in layer_info else "Lädt noch..."}'
                })
            
            layer = layer_info['layer']
            
            # Temporäre Datei für den Export erstellen
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format.lower()}') as tmp:
                # Export-Optionen konfigurieren
                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = {
                    'GEOJSON': 'GeoJSON',
                    'GPKG': 'GPKG',
                    'SHAPEFILE': 'ESRI Shapefile'
                }.get(output_format)
                
                if not options.driverName:
                    return jsonify({'status': 'error', 'message': 'Nicht unterstütztes Format'})
                
                logger.info(f"Exportiere Layer {layer.name()} nach {tmp.name}")
                
                # Layer exportieren
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    layer,
                    tmp.name,
                    'UTF-8',
                    QgsCoordinateReferenceSystem('EPSG:4326'),
                    options.driverName
                )
                
                if error[0] != QgsVectorFileWriter.NoError:
                    logger.error(f"Fehler beim Export: {error}")
                    return jsonify({'status': 'error', 'message': 'Fehler beim Export der Daten'})
                
                # Prüfe die Dateigröße
                file_size = os.path.getsize(tmp.name)
                logger.info(f"Exportierte Dateigröße: {file_size / 1024 / 1024:.2f} MB")
                
                if file_size == 0:
                    logger.error("Exportierte Datei ist leer")
                    return jsonify({'status': 'error', 'message': 'Keine Daten exportiert'})
                
                logger.info(f"Download erfolgreich vorbereitet: {tmp.name}")
                
                # Layer aus Cache entfernen
                remove_from_layer_cache(cache_id)
                
                return send_file(
                    tmp.name,
                    as_attachment=True,
                    download_name=f"{layer.name().replace(':', '_')}.{output_format.lower()}"
                )
                    
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Download: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/get_layer_info', methods=['POST'])
def get_layer_info():
    """Lädt Layer-Informationen ohne Download"""
    try:
        wfs_url = request.form.get('wfs_url')
        layer_name = request.form.get('layer_name')
        
        if not wfs_url or not layer_name:
            return jsonify({'status': 'error', 'message': 'URL oder Layer-Name fehlt'})
        
        logger.info(f"Lade Layer-Info für: {layer_name}")
        
        # WFS Version automatisch erkennen
        version = get_working_wfs_version(wfs_url)
        if not version:
            return jsonify({'status': 'error', 'message': 'Keine kompatible WFS-Version gefunden'})
        
        # WFS Layer mit QGIS laden
        uri = QgsDataSourceUri()
        uri.setParam('url', wfs_url)
        uri.setParam('typename', layer_name)
        uri.setParam('version', version)
        uri.setParam('srsname', 'EPSG:4326')
        uri.setParam('pagingEnabled', 'false')
        
        logger.info(f"WFS URI: {uri.uri()}")
        
        # Layer erstellen
        layer = QgsVectorLayer(uri.uri(), layer_name, 'WFS')
        
        if not layer.isValid():
            error = layer.error()
            logger.error(f"Layer konnte nicht geladen werden - Fehler: {error.summary()}")
            return jsonify({
                'status': 'error',
                'message': f'Layer konnte nicht geladen werden: {error.summary()}'
            })
        
        # Warte maximal 10 Sekunden auf erste Features
        start_time = time.time()
        feature_count = 0
        while time.time() - start_time < 10:
            feature_count = layer.featureCount()
            if feature_count > 0:
                break
            time.sleep(0.5)
        
        # Layer aus QGIS entfernen
        QgsProject.instance().removeMapLayer(layer)
        
        return jsonify({
            'status': 'success',
            'feature_count': feature_count,
            'message': f'Layer enthält {feature_count} Features'
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Layer-Info: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Fehler beim Laden der Layer-Info: {str(e)}'
        })

# ATKIS Handbuch Verarbeitung
def init_atkis_processor():
    """Initialisiert den ATKIS-Prozessor mit dem Handbuch"""
    global atkis_knowledge
    try:
        # PDF laden (Pfad muss angepasst werden)
        loader = PyPDFLoader("docs/atkis_handbook.pdf")
        pages = loader.load_and_split()
        
        # Text in Chunks aufteilen für bessere Verarbeitung
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        atkis_knowledge = text_splitter.split_documents(pages)
        logger.info("ATKIS Handbuch erfolgreich geladen")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Laden des ATKIS Handbuchs: {str(e)}")
        return False

def process_atkis_layer(layer_name, layer_title):
    """Verarbeitet einen ATKIS Layer mit KI-Unterstützung"""
    if not layer_name.startswith('ax_'):
        return layer_title
        
    try:
        # OpenAI API für Analyse nutzen
        llm = OpenAI(temperature=0)
        
        # Kontext aus dem Handbuch suchen
        relevant_context = []
        for chunk in atkis_knowledge:
            if layer_name[3:] in chunk.page_content.lower():
                relevant_context.append(chunk.page_content)
        
        if not relevant_context:
            return layer_title
            
        # KI-Prompt erstellen
        prompt = f"""
        Basierend auf dem ATKIS-Handbuch, analysiere den Layer '{layer_name}'.
        
        Kontext aus dem Handbuch:
        {' '.join(relevant_context[:3])}
        
        Gib einen präzisen, deutschen Titel für diesen Layer, der seine Funktion beschreibt.
        Antworte NUR mit dem neuen Titel, keine weiteren Erklärungen.
        """
        
        # Neuen Titel generieren
        new_title = llm.predict(prompt).strip()
        logger.info(f"Layer {layer_name} umbenannt zu: {new_title}")
        return new_title
        
    except Exception as e:
        logger.error(f"Fehler bei der ATKIS-Verarbeitung: {str(e)}")
        return layer_title

# Initialisiere ATKIS-Prozessor beim Start
atkis_knowledge = []
init_atkis_processor()

def process_atkis_attributes(layer_name, attributes):
    """Verarbeitet die Attributwerte eines ATKIS Layers mit KI-Unterstützung"""
    try:
        llm = OpenAI(temperature=0)
        
        # Kontext aus dem Handbuch suchen
        relevant_context = []
        for chunk in atkis_knowledge:
            if layer_name[3:] in chunk.page_content.lower():
                relevant_context.append(chunk.page_content)
        
        if not relevant_context:
            return attributes
            
        # Für jedes Attribut eine Beschreibung generieren
        translated_attributes = {}
        for attr_name, attr_value in attributes.items():
            prompt = f"""
            Basierend auf dem ATKIS-Handbuch, interpretiere das Attribut '{attr_name}' mit Wert '{attr_value}' für den Layer '{layer_name}'.
            
            Kontext aus dem Handbuch:
            {' '.join(relevant_context[:3])}
            
            Gib eine kurze, präzise deutsche Erklärung für diesen Attributwert.
            Antworte NUR mit der Erklärung, keine weiteren Kommentare.
            """
            
            explanation = llm.predict(prompt).strip()
            translated_attributes[attr_name] = {
                'original': attr_value,
                'explanation': explanation
            }
            
        return translated_attributes
        
    except Exception as e:
        logger.error(f"Fehler bei der ATKIS-Attribut-Verarbeitung: {str(e)}")
        return attributes

@app.route('/get_attributes', methods=['POST'])
def get_attributes():
    """Lädt die Attributtabelle eines Layers und interpretiert die Werte"""
    try:
        wfs_url = request.form.get('wfs_url')
        layer_name = request.form.get('layer_name')
        page = int(request.form.get('page', 1))
        page_size = int(request.form.get('page_size', 50))
        
        if not wfs_url or not layer_name:
            return jsonify({'status': 'error', 'message': 'URL oder Layer-Name fehlt'})
        
        # WFS Layer laden
        uri = QgsDataSourceUri()
        uri.setParam('url', wfs_url)
        uri.setParam('typename', layer_name)
        uri.setParam('version', get_working_wfs_version(wfs_url))
        uri.setParam('srsname', 'EPSG:4326')
        
        layer = QgsVectorLayer(uri.uri(), layer_name, 'WFS')
        
        if not layer.isValid():
            return jsonify({
                'status': 'error',
                'message': 'Layer konnte nicht geladen werden'
            })
        
        # Gesamtanzahl der Features
        total_features = layer.featureCount()
        total_pages = math.ceil(total_features / page_size)
        
        # Attribute und ihre Typen sammeln
        fields = layer.fields()
        attribute_info = {}
        for field in fields:
            attribute_info[field.name()] = {
                'type': field.typeName(),
                'values': []
            }
        
        # Features für aktuelle Seite laden
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        features = []
        for i, feature in enumerate(layer.getFeatures()):
            if i < start_index:
                continue
            if i >= end_index:
                break
                
            feature_data = {}
            for field in fields:
                value = feature[field.name()]
                feature_data[field.name()] = value
                # Sammle eindeutige Werte für jedes Attribut
                if value not in attribute_info[field.name()]['values']:
                    attribute_info[field.name()]['values'].append(value)
            
            features.append(feature_data)
        
        # ATKIS-spezifische Verarbeitung der Attributwerte
        if layer_name.startswith('ax_'):
            translated_features = []
            for feature in features:
                translated_feature = process_atkis_attributes(layer_name, feature)
                translated_features.append(translated_feature)
            features = translated_features
        
        return jsonify({
            'status': 'success',
            'features': features,
            'attribute_info': attribute_info,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'page_size': page_size,
                'total_features': total_features
            },
            'is_atkis': layer_name.startswith('ax_')
        })
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Attribute: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/sync_atkis_names', methods=['POST'])
def sync_atkis_names():
    """Synchronisiert ATKIS-Attributnamen mit KI-Unterstützung"""
    try:
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Content-Type muss application/json sein'
            }), 400
            
        data = request.get_json()
        attributes = data.get('attributes')
        layer_name = data.get('layer_name')
        is_atkis = data.get('is_atkis', False)  # Neue Option für manuelle ATKIS-Markierung
        
        logger.info(f"Starte Synchronisierung für Layer {layer_name} (ATKIS: {is_atkis})")
        
        if not attributes or not layer_name:
            return jsonify({
                'status': 'error',
                'message': 'Keine Attribute oder Layer-Name angegeben'
            }), 400
            
        if not is_atkis:
            return jsonify({
                'status': 'error',
                'message': 'Layer ist nicht als ATKIS markiert'
            }), 400
            
        if not os.getenv('OPENAI_API_KEY'):
            return jsonify({
                'status': 'error',
                'message': 'OpenAI API-Key nicht konfiguriert'
            }), 500
            
        llm = OpenAI(temperature=0)
        
        # Kontext aus dem Handbuch suchen
        relevant_context = []
        search_term = layer_name[3:] if layer_name.startswith('ax_') else layer_name
        for chunk in atkis_knowledge:
            if search_term.lower() in chunk.page_content.lower():
                relevant_context.append(chunk.page_content)
        
        if not relevant_context:
            logger.warning(f"Keine Kontextinformationen für Layer {layer_name} gefunden")
            return jsonify({
                'status': 'error',
                'message': 'Keine Kontextinformationen im ATKIS-Handbuch gefunden'
            }), 404
        
        logger.info(f"Gefundene Kontexte: {len(relevant_context)}")
        
        # Verbesserte Prompts für verschiedene Attributtypen
        translated_attributes = {}
        for attr_name, attr_value in attributes.items():
            try:
                # Basis-Kontext für den Prompt
                context = ' '.join(relevant_context[:3])
                
                # Spezifischer Prompt je nach Attributtyp
                if isinstance(attr_value, (list, tuple)):
                    prompt = f"""
                    Aufgabe: Interpretiere den ATKIS-Attributwert für '{attr_name}' im Layer '{layer_name}'.
                    
                    Kontext aus dem ATKIS-Handbuch:
                    {context}
                    
                    Attributwerte: {', '.join(map(str, attr_value))}
                    
                    Anforderungen:
                    1. Gib eine präzise, fachlich korrekte Erklärung der möglichen Werte
                    2. Verwende ATKIS-Fachterminologie
                    3. Behalte den technischen Kontext bei
                    4. Formuliere in klarem, verständlichem Deutsch
                    5. Maximale Länge: 200 Zeichen
                    
                    Antwort nur mit der Erklärung, keine Einleitung oder zusätzliche Kommentare.
                    """
                else:
                    prompt = f"""
                    Aufgabe: Interpretiere den ATKIS-Attributwert für '{attr_name}' im Layer '{layer_name}'.
                    
                    Kontext aus dem ATKIS-Handbuch:
                    {context}
                    
                    Attributwert: {attr_value}
                    
                    Anforderungen:
                    1. Gib eine präzise, fachlich korrekte Erklärung des Wertes
                    2. Verwende ATKIS-Fachterminologie
                    3. Behalte den technischen Kontext bei
                    4. Formuliere in klarem, verständlichem Deutsch
                    5. Maximale Länge: 200 Zeichen
                    
                    Antwort nur mit der Erklärung, keine Einleitung oder zusätzliche Kommentare.
                    """
                
                logger.info(f"Verarbeite Attribut: {attr_name}")
                explanation = llm.predict(prompt).strip()
                translated_attributes[attr_name] = {
                    'original': attr_value,
                    'explanation': explanation
                }
                logger.info(f"Attribut {attr_name} erfolgreich übersetzt")
                
            except Exception as e:
                logger.error(f"Fehler bei der Übersetzung von Attribut {attr_name}: {str(e)}")
                translated_attributes[attr_name] = {
                    'original': attr_value,
                    'explanation': f"Fehler bei der Übersetzung: {str(e)}"
                }
        
        logger.info(f"Synchronisierung für Layer {layer_name} abgeschlossen")
        return jsonify({
            'status': 'success',
            'attributes': translated_attributes
        })
        
    except Exception as e:
        logger.error(f"Fehler bei der ATKIS-Namensynchronisierung: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_db_connection():
    """Stellt eine Verbindung zur SQLite-Datenbank her"""
    try:
        conn = sqlite3.connect('src/backend/database.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Fehler beim Verbinden zur Datenbank: {str(e)}")
        raise

@app.route('/api/download/<layer_id>')
def download_layer(layer_id):
    try:
        format = request.args.get('format', 'geojson')
        
        # Layer aus dem Cache holen
        with layer_cache_lock:
            if layer_id not in layer_cache:
                return jsonify({'error': 'Layer nicht gefunden'}), 404
            layer_data = layer_cache[layer_id]
        
        # Temporäre Datei erstellen
        with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as tmp:
            if format == 'geojson':
                # GeoJSON direkt speichern
                json.dump(layer_data, tmp)
            elif format == 'shapefile':
                # Konvertierung zu Shapefile mit GeoPandas
                gdf = gpd.GeoDataFrame.from_features(layer_data['features'])
                gdf.to_file(tmp.name, driver='ESRI Shapefile')
            else:
                return jsonify({'error': 'Ungültiges Format'}), 400
            
            tmp_path = tmp.name
        
        # Datei senden und danach löschen
        @after_this_request
        def remove_file(response):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.error(f'Fehler beim Löschen der temporären Datei: {e}')
            return response
        
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=f'{layer_id}.{format}',
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f'Fehler beim Download: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync-atkis/<layer_id>', methods=['POST'])
def sync_atkis(layer_id):
    try:
        # Layer aus dem Cache holen
        with layer_cache_lock:
            if layer_id not in layer_cache:
                return jsonify({'error': 'Layer nicht gefunden'}), 404
            layer_data = layer_cache[layer_id]
        
        # OpenAI für ATKIS-Optimierung initialisieren
        llm = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Features durchgehen und Namen optimieren
        for feature in layer_data['features']:
            if 'properties' in feature:
                # Aktuelle Eigenschaften als Kontext sammeln
                properties = feature['properties']
                
                # ATKIS-spezifischen Kontext erstellen
                atkis_context = []
                if 'objektart' in properties:
                    atkis_context.append(f"Objektart: {properties['objektart']}")
                if 'funktion' in properties:
                    atkis_context.append(f"Funktion: {properties['funktion']}")
                if 'zustand' in properties:
                    atkis_context.append(f"Zustand: {properties['zustand']}")
                
                context = ' '.join(atkis_context) if atkis_context else ' '.join(str(v) for v in properties.values())
                
                # KI-Prompt für ATKIS-spezifische Namensgebung
                prompt = f"""
                Generiere einen standardisierten ATKIS-konformen Namen für ein geografisches Feature mit folgenden Eigenschaften:
                {context}

                Anforderungen:
                1. Verwende ATKIS-Fachterminologie
                2. Maximale Länge: 50 Zeichen
                3. Struktur: [Objektart] [Funktion/Zustand] [Zusatzinfo]
                4. Nur relevante Informationen einbeziehen
                5. Keine Abkürzungen außer ATKIS-Standard

                Antworte NUR mit dem generierten Namen.
                """
                
                # Neuen Namen generieren
                response = llm.generate(prompt)
                new_name = response.strip()
                
                # Namen aktualisieren
                feature['properties']['display_name'] = new_name
                
                # Zusätzliche ATKIS-spezifische Attribute übersetzen
                for key, value in properties.items():
                    if key in ['objektart', 'funktion', 'zustand', 'art']:
                        translation_prompt = f"""
                        Übersetze den ATKIS-Attributwert:
                        Attribut: {key}
                        Wert: {value}
                        
                        Gib eine kurze, fachlich korrekte Erklärung in maximal 100 Zeichen.
                        Antworte NUR mit der Übersetzung.
                        """
                        translated_value = llm.generate(translation_prompt).strip()
                        feature['properties'][f'{key}_beschreibung'] = translated_value
        
        # Aktualisierten Layer im Cache speichern
        with layer_cache_lock:
            layer_cache[layer_id] = layer_data
        
        return jsonify({
            'success': True,
            'message': 'ATKIS-Namen erfolgreich synchronisiert',
            'reloadRequired': True
        })
        
    except Exception as e:
        logger.error(f'Fehler bei der ATKIS-Synchronisierung: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-attributes/<layer_id>', methods=['POST'])
def update_attributes(layer_id):
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type muss application/json sein'}), 400
            
        data = request.get_json()
        updated_features = data.get('features')
        
        if not updated_features:
            return jsonify({'error': 'Keine aktualisierten Features gefunden'}), 400
        
        # Layer aus dem Cache holen
        with layer_cache_lock:
            if layer_id not in layer_cache:
                return jsonify({'error': 'Layer nicht gefunden'}), 404
            layer_data = layer_cache[layer_id]
        
        # Features aktualisieren
        for i, feature in enumerate(layer_data['features']):
            if i < len(updated_features) and updated_features[i]:
                feature['properties'].update(updated_features[i])
        
        # Aktualisierten Layer im Cache speichern
        with layer_cache_lock:
            layer_cache[layer_id] = layer_data
        
        return jsonify({
            'success': True,
            'message': 'Attribute erfolgreich aktualisiert'
        })
        
    except Exception as e:
        logger.error(f'Fehler beim Aktualisieren der Attribute: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync-atkis-all', methods=['POST'])
def sync_atkis_all():
    try:
        # Alle Layer aus dem Cache holen
        with layer_cache_lock:
            layer_ids = list(layer_cache.keys())
        
        # OpenAI für ATKIS-Optimierung initialisieren
        llm = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # ATKIS-Handbuch laden
        atkis_handbook = load_atkis_handbook()
        
        # Jeden Layer verarbeiten
        for layer_id in layer_ids:
            with layer_cache_lock:
                layer_data = layer_cache[layer_id]
            
            # Features durchgehen und Namen optimieren
            for feature in layer_data['features']:
                if 'properties' in feature:
                    properties = feature['properties']
                    
                    # ATKIS-spezifischen Kontext erstellen
                    atkis_context = []
                    if 'objektart' in properties:
                        atkis_context.append(f"Objektart: {properties['objektart']}")
                    if 'funktion' in properties:
                        atkis_context.append(f"Funktion: {properties['funktion']}")
                    if 'zustand' in properties:
                        atkis_context.append(f"Zustand: {properties['zustand']}")
                    
                    # Relevante Informationen aus dem Handbuch suchen
                    handbook_context = search_atkis_handbook(atkis_handbook, properties)
                    
                    context = ' '.join(atkis_context) if atkis_context else ' '.join(str(v) for v in properties.values())
                    if handbook_context:
                        context += f"\n\nATKIS-Handbuch Kontext:\n{handbook_context}"
                    
                    # KI-Prompt für ATKIS-spezifische Namensgebung
                    prompt = f"""
                    Generiere einen standardisierten ATKIS-konformen Namen für ein geografisches Feature mit folgenden Eigenschaften:
                    {context}

                    Anforderungen:
                    1. Verwende ATKIS-Fachterminologie
                    2. Maximale Länge: 50 Zeichen
                    3. Struktur: [Objektart] [Funktion/Zustand] [Zusatzinfo]
                    4. Nur relevante Informationen einbeziehen
                    5. Keine Abkürzungen außer ATKIS-Standard

                    Antworte NUR mit dem generierten Namen.
                    """
                    
                    # Neuen Namen generieren
                    response = llm.generate(prompt)
                    new_name = response.strip()
                    
                    # Namen aktualisieren
                    feature['properties']['display_name'] = new_name
                    
                    # Zusätzliche ATKIS-spezifische Attribute übersetzen
                    for key, value in properties.items():
                        if key in ['objektart', 'funktion', 'zustand', 'art']:
                            translation_prompt = f"""
                            Übersetze den ATKIS-Attributwert basierend auf dem ATKIS-Handbuch:
                            Attribut: {key}
                            Wert: {value}
                            
                            Kontext aus dem Handbuch:
                            {handbook_context}
                            
                            Gib eine kurze, fachlich korrekte Erklärung in maximal 100 Zeichen.
                            Antworte NUR mit der Übersetzung.
                            """
                            translated_value = llm.generate(translation_prompt).strip()
                            feature['properties'][f'{key}_beschreibung'] = translated_value
            
            # Aktualisierten Layer im Cache speichern
            with layer_cache_lock:
                layer_cache[layer_id] = layer_data
        
        return jsonify({
            'success': True,
            'message': 'ATKIS-Namen für alle Layer synchronisiert',
            'reloadRequired': True
        })
        
    except Exception as e:
        logger.error(f'Fehler bei der ATKIS-Synchronisierung aller Layer: {str(e)}')
        return jsonify({'error': str(e)}), 500

def load_atkis_handbook():
    """Lädt das ATKIS-Handbuch aus der PDF"""
    try:
        handbook_path = os.path.join(os.path.dirname(__file__), '../../docs/atkis_handbook.pdf')
        loader = PyPDFLoader(handbook_path)
        pages = loader.load_and_split()
        
        # Text in Chunks aufteilen
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        return text_splitter.split_documents(pages)
    except Exception as e:
        logger.error(f'Fehler beim Laden des ATKIS-Handbuchs: {str(e)}')
        return []

def search_atkis_handbook(handbook_pages, properties):
    """Sucht relevante Informationen im ATKIS-Handbuch"""
    try:
        relevant_text = []
        search_terms = [
            properties.get('objektart', ''),
            properties.get('funktion', ''),
            properties.get('zustand', ''),
            properties.get('art', '')
        ]
        
        for page in handbook_pages:
            for term in search_terms:
                if term and term.lower() in page.page_content.lower():
                    relevant_text.append(page.page_content)
                    break
        
        return '\n'.join(relevant_text[:3])  # Nur die ersten 3 relevanten Abschnitte
    except Exception as e:
        logger.error(f'Fehler bei der ATKIS-Handbuch-Suche: {str(e)}')
        return ''

@app.route('/api/clean-layer-names', methods=['POST'])
def clean_layer_names():
    """Säubert und strukturiert Layer-Namen"""
    try:
        data = request.get_json()
        logger.info("Empfangene Daten: %s", data)
        
        if not data or 'layers' not in data:
            logger.error("Keine Layer-Informationen gefunden in: %s", data)
            return jsonify({'error': 'Keine Layer-Informationen gefunden'}), 400
            
        layers = data['layers']
        logger.info("Anzahl der zu verarbeitenden Layer: %d", len(layers))
        
        # OpenAI initialisieren
        llm = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if not os.getenv('OPENAI_API_KEY'):
            logger.error("OpenAI API Key nicht gefunden!")
            return jsonify({'error': 'OpenAI API Key nicht konfiguriert'}), 500
        
        # Verarbeite alle Layer auf einmal
        layer_names = "\n".join([f"- {layer['name']}: {layer['title']}" for layer in layers])
        logger.info("Zusammengestellte Layer-Namen: %s", layer_names)
        
        user_prompt = f"""Hier ist eine Liste von Layer-Namen, die gesäubert werden müssen. 
        Formatiere jeden Namen nach diesen Regeln:

        Layer-Liste:
        {layer_names}

        Formatierungsregeln:
        1. Verwende Unterstriche (_) zwischen Wörtern
        2. Entferne unlogische Präfixe/Suffixe (z.B. 'data_', '_temp', Zahlen am Ende)
        3. Nutze klare deutsche Begriffe
        4. Behalte fachliche Bezeichnungen
        5. Maximale Länge: 50 Zeichen
        6. Kleinschreibung, außer bei Abkürzungen
        7. Format: [hauptkategorie]_[unterkategorie]_[spezifikation]

        Beispiele:
        - "BaulandParzelleGross123" → "bauland_parzelle_gross"
        - "STRASSENABSCHNITT_HAUPT" → "strasse_hauptweg"
        - "gewaesser_FLUSS_data" → "gewaesser_fluss"

        Antworte EXAKT in diesem Format (eine Zeile pro Layer):
        original_name|neuer_name
        """

        try:
            logger.info("Sende Prompt an OpenAI")
            response = llm.predict(user_prompt).strip()
            logger.info("Antwort von OpenAI: %s", response)
            
            # Verarbeite die Antwort
            cleaned_layers = []
            for line in response.split('\n'):
                logger.info("Verarbeite Zeile: %s", line)
                if '|' in line:
                    original_id, new_name = line.strip().split('|')
                    original_id = original_id.strip()
                    new_name = new_name.strip()
                    logger.info("Aufgeteilte Werte - Original: '%s', Neu: '%s'", original_id, new_name)
                    
                    # Finde den ursprünglichen Layer
                    matching_layer = None
                    for layer in layers:
                        if layer['name'] == original_id:
                            matching_layer = layer
                            break
                    
                    if matching_layer:
                        cleaned_layer = {
                            'id': matching_layer['name'],
                            'name': matching_layer['name'],
                            'title': new_name,
                            'namespace': matching_layer.get('namespace', '')
                        }
                        cleaned_layers.append(cleaned_layer)
                        logger.info("Layer hinzugefügt: %s", cleaned_layer)
                    else:
                        logger.warning("Kein passender Layer gefunden für: %s", original_id)
            
            logger.info("Erfolgreich verarbeitete Layer: %d", len(cleaned_layers))
            return jsonify({
                'status': 'success',
                'message': 'Layer-Namen wurden erfolgreich gesäubert',
                'layers': cleaned_layers
            })
            
        except Exception as e:
            logger.error("Fehler bei der KI-Verarbeitung: %s", str(e), exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Fehler bei der KI-Verarbeitung: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error("Allgemeiner Fehler bei der Namenssäuberung: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)