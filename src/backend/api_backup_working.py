from flask import Flask, jsonify, request, render_template, send_file, Response, stream_with_context
from flask_cors import CORS
import os
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
    QgsFeatureRequest
)
from threading import Lock, Thread
from PyQt5.QtCore import QThread
import zipfile

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

app = Flask(__name__, template_folder='../../templates')
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

@app.route('/prepare_download', methods=['POST'])
def prepare_download():
    """Lädt den Layer in QGIS und exportiert ihn direkt"""
    try:
        wfs_url = request.form.get('wfs_url')
        layer_name = request.form.get('layer_name')
        output_format = request.form.get('format', 'GEOJSON').upper()
        
        if not wfs_url or not layer_name:
            return jsonify({'status': 'error', 'message': 'URL oder Layer-Name fehlt'}), 400
        
        logger.info(f"Starte Download für Layer: {layer_name} im Format {output_format}")
        
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
        
        # Warte bis Features geladen sind (maximal 30 Sekunden)
        start_time = time.time()
        last_count = 0
        while True:
            current_count = layer.featureCount()
            if current_count > 0 and current_count == last_count:
                # Features wurden geladen
                break
                
            if time.time() - start_time > 30:
                QgsProject.instance().removeMapLayer(layer)
                return jsonify({
                    'status': 'error',
                    'message': 'Zeitüberschreitung beim Laden des Layers'
                }), 408
                
            last_count = current_count
            time.sleep(0.5)  # Warte 500ms zwischen den Checks
            
        logger.info(f"Layer geladen mit {current_count} Features")
        
        # Temporäre Datei für den Export erstellen
        try:
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
                QgsProject.instance().removeMapLayer(layer)
                return jsonify({'status': 'error', 'message': 'Nicht unterstütztes Format'}), 400
                
            config = format_config[output_format]
            
            # Erstelle temporäres Verzeichnis für Shapefile
            if output_format == 'SHAPEFILE':
                tmp_dir = tempfile.mkdtemp()
                output_path = os.path.join(tmp_dir, 'output.shp')
            else:
                # Für andere Formate nur temporäre Datei
                tmp_dir = None
                with tempfile.NamedTemporaryFile(delete=False, suffix=config['ext']) as tmp:
                    output_path = tmp.name
            
            logger.info(f"Exportiere Layer nach {output_path}")
            
            # Layer exportieren
            error = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                output_path,
                'UTF-8',
                layer.crs(),
                config['driver']
            )
            
            # Layer aus QGIS entfernen
            QgsProject.instance().removeMapLayer(layer)
            
            if isinstance(error, tuple):
                error = error[0]  # Neuere QGIS-Versionen
                
            if error != QgsVectorFileWriter.NoError:
                logger.error(f"Fehler beim Export: {error}")
                return jsonify({'status': 'error', 'message': 'Fehler beim Export der Daten'}), 500
            
            # Bei Shapefile alle Dateien in ein ZIP-Archiv packen
            if output_format == 'SHAPEFILE':
                zip_path = os.path.join(tmp_dir, 'output.zip')
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                        file_path = output_path.replace('.shp', ext)
                        if os.path.exists(file_path):
                            zipf.write(file_path, os.path.basename(file_path))
                output_path = zip_path
            
            # Prüfe die Dateigröße
            file_size = os.path.getsize(output_path)
            logger.info(f"Exportierte Dateigröße: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size == 0:
                return jsonify({'status': 'error', 'message': 'Keine Daten exportiert'}), 500
            
            try:
                download_name = f"{layer_name.replace(':', '_')}{config['ext']}"
                response = send_file(
                    output_path,
                    as_attachment=True,
                    download_name=download_name,
                    mimetype=config['mime']
                )
                response.headers['Content-Type'] = config['mime']
                return response
            except Exception as e:
                logger.error(f"Fehler beim Senden der Datei: {str(e)}")
                return jsonify({'status': 'error', 'message': 'Fehler beim Senden der Datei'}), 500
            finally:
                # Aufräumen
                if tmp_dir and os.path.exists(tmp_dir):
                    import shutil
                    shutil.rmtree(tmp_dir)
                elif os.path.exists(output_path):
                    os.unlink(output_path)
                    
        except Exception as e:
            logger.error(f"Fehler beim Export: {str(e)}")
            if tmp_dir and os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)
            return jsonify({'status': 'error', 'message': f'Fehler beim Export: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Fehler beim Download: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True, port=5001)