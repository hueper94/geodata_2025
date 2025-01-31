from flask import Flask, request, jsonify, render_template
import os
import logging
from utils.openai_helper import OpenAIHelper
from utils.auto_debugger import auto_debug, AutoDebugger
import requests
import xml.etree.ElementTree as ET
import sqlite3
import json
import re
from config.environment import config

# Logger Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Konfiguration laden
    app.config.from_object(config[config_name])
    
    # Logging einrichten
    log_filename = f"logs/{config_name}_website.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.DEBUG if app.config['DEBUG'] else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Datenbank-Name basierend auf Umgebung
    app.config['DATABASE'] = os.path.join('database', app.config['DATABASE_NAME'])
    
    # Auto-Debugger initialisieren
    debugger = AutoDebugger()

    # OpenAI Helper initialisieren
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    config_path = os.path.join(config_dir, 'config.json')
    ai_helper = OpenAIHelper(config_path=config_path)

    @app.route('/')
    def overview():
        return render_template('overview.html')

    @app.route('/data_lexicon')
    def data_lexicon():
        """Zeigt das Datenlexikon an"""
        try:
            logger.info("=== Start: Lade Datenlexikon ===")
            conn = sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)
            cursor = conn.cursor()
            
            # Debug: Zeige Tabellen
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            logger.info(f"Verfügbare Tabellen: {tables}")
            
            # Debug: Zeige Spalten der wfs_layers Tabelle
            cursor.execute("PRAGMA table_info(wfs_layers);")
            columns = cursor.fetchall()
            logger.info(f"Spalten in wfs_layers: {columns}")
            
            # Hole alle Layer mit ihren Details
            cursor.execute('''
                SELECT 
                    id, name, title, description, 
                    source_type, source_url, state,
                    strftime('%Y-%m-%d', created_at) as created_date,
                    strftime('%Y-%m-%d', last_updated) as updated_date
                FROM wfs_layers 
                ORDER BY created_at DESC
            ''')
            
            layers = cursor.fetchall()
            logger.info(f"Gefundene Layer: {len(layers)}")
            
            # Debug: Zeige die ersten paar Layer
            if layers:
                logger.info(f"Erster Layer: {layers[0]}")
            else:
                logger.warning("Keine Layer in der Datenbank gefunden!")
                
                # Debug: Prüfe ob Layer existieren
                cursor.execute("SELECT COUNT(*) FROM wfs_layers")
                count = cursor.fetchone()[0]
                logger.info(f"Anzahl Layer in der Datenbank: {count}")
            
            logger.info("=== Ende: Datenlexikon geladen ===")
            return render_template('data_lexicon.html', layers=layers)
            
        except Exception as e:
            logger.error(f"Fehler beim Laden des Lexikons: {str(e)}")
            return render_template('data_lexicon.html', layers=[], error=str(e))
        finally:
            if 'conn' in locals():
                conn.close()

    @app.route('/wfs_wms_explorer')
    def wfs_wms_explorer():
        return render_template('wfs_wms_explorer.html')

    @app.route('/import_to_lexicon', methods=['POST'])
    @auto_debug
    def import_to_lexicon():
        """Importiert Layer in das Lexikon"""
        try:
            debugger.start_debug_session()
            data = request.get_json()
            
            # Debug-Logging
            logger.info(f"Empfangene Daten: {data}")
            
            if not data:
                logger.error("Keine Daten empfangen")
                return jsonify({
                    'status': 'error',
                    'message': 'Keine Daten zum Import gefunden'
                })
                
            if 'layers' not in data:
                logger.error("Keine Layer in den Daten gefunden")
                return jsonify({
                    'status': 'error',
                    'message': 'Keine Layer zum Import gefunden'
                })
                
            layers = data['layers']
            service_url = data.get('service_url')
            service_type = data.get('service_type', 'WFS')
            
            logger.info(f"Verarbeite {len(layers)} Layer von {service_url} ({service_type})")
            
            # Erkenne Bundesland
            state = detect_state(service_url)
            logger.info(f"Erkanntes Bundesland: {state}")
            
            # Bereite Batch vor
            layer_batch = []
            imported = 0
            
            # Verarbeite Layer
            for namespace, ns_layers in layers.items():
                logger.info(f"Verarbeite Namespace: {namespace}")
                for layer_name, layer_info in ns_layers.items():
                    logger.info(f"Verarbeite Layer: {layer_name}")
                    lexicon_entry = {
                        'name': layer_info['name'],
                        'title': layer_info.get('title', ''),
                        'description': layer_info.get('description', ''),
                        'source_url': service_url,
                        'source_type': service_type,
                        'state': state,
                        'attributes': layer_info.get('attributes', [])
                    }
                    layer_batch.append(lexicon_entry)
            
            # Importiere alle Layer
            if layer_batch:
                try:
                    logger.info(f"Starte Import von {len(layer_batch)} Layern")
                    import_layer_batch(layer_batch)
                    imported = len(layer_batch)
                    logger.info(f'{imported} Layer ins Lexikon importiert')
                except Exception as e:
                    logger.error(f"Fehler beim Import: {str(e)}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Fehler beim Import: {str(e)}'
                    })
            
            return jsonify({
                'status': 'success',
                'imported_layers': imported,
                'message': f'{imported} Layer erfolgreich ins Lexikon importiert'
            })
            
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Import ins Lexikon: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            })

    @app.route('/get_layers', methods=['POST'])
    @auto_debug
    def get_layers():
        """Holt Layer von einem WFS/WMS Service"""
        try:
            debugger.start_debug_session()
            debugger.log_step('Start Layer-Abruf')
            
            service_url = request.form.get('wfs_url')
            logger.info(f'Service-URL empfangen: {service_url}')
            
            if not service_url:
                return jsonify({
                    'status': 'error',
                    'message': 'Keine Service-URL angegeben'
                })

            # Versuche zuerst als WFS
            try:
                layers = get_wfs_layers(service_url)
                service_type = 'WFS'
            except Exception as wfs_error:
                logger.info(f'WFS-Abruf fehlgeschlagen, versuche WMS: {str(wfs_error)}')
                try:
                    layers = get_wms_layers(service_url)
                    service_type = 'WMS'
                except Exception as wms_error:
                    logger.error(f'Beide Service-Typen fehlgeschlagen - WFS: {str(wfs_error)}, WMS: {str(wms_error)}')
                    return jsonify({
                        'status': 'error',
                        'message': 'Service nicht erkannt oder nicht erreichbar'
                    })

            return jsonify({
                'status': 'success',
                'service_type': service_type,
                'layers': layers,
                'service_url': service_url,
                'message': f'{service_type} erfolgreich geladen'
            })
            
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Fehler beim Laden der Layer: {str(e)}'
            })

    def get_wfs_layers(url):
        """Holt Layer von einem WFS-Service"""
        params = {
            'service': 'WFS',
            'request': 'GetCapabilities'
        }
        
        response = requests.get(url, params=params, verify=False, timeout=30)
        if response.status_code != 200:
            raise Exception(f'WFS-Server antwortet nicht (Status: {response.status_code})')

        root = ET.fromstring(response.content)
        namespaces = {
            'wfs': 'http://www.opengis.net/wfs/2.0',
            'wfs1': 'http://www.opengis.net/wfs',
            'ows': 'http://www.opengis.net/ows/1.1',
            'ows2': 'http://www.opengis.net/ows'
        }

        layers = {}
        feature_types = []

        # Suche FeatureTypes
        for xpath in ['.//wfs:FeatureType', './/wfs1:FeatureType', './/FeatureType']:
            feature_types = root.findall(xpath, namespaces)
            if feature_types:
                break

        if not feature_types:
            raise Exception('Keine Layer im WFS-Dienst gefunden')

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

            abstract = None
            for abstract_path in ['Abstract', 'wfs:Abstract', 'wfs1:Abstract']:
                abstract_elem = feature_type.find(abstract_path, namespaces)
                if abstract_elem is not None:
                    abstract = abstract_elem.text
                    break

            title = title or name
            namespace = name.split(':')[0] if ':' in name else 'default'
            layer_name = name.split(':')[1] if ':' in name else name

            if namespace not in layers:
                layers[namespace] = {}

            layers[namespace][layer_name] = {
                'name': name,
                'title': title,
                'description': abstract or '',
                'attributes': []  # Attribute werden später geladen
            }

        return layers

    def get_wms_layers(url):
        """Holt Layer von einem WMS-Service"""
        params = {
            'service': 'WMS',
            'request': 'GetCapabilities'
        }
        
        response = requests.get(url, params=params, verify=False, timeout=30)
        if response.status_code != 200:
            raise Exception(f'WMS-Server antwortet nicht (Status: {response.status_code})')

        root = ET.fromstring(response.content)
        namespaces = {
            'wms': 'http://www.opengis.net/wms'
        }

        layers = {}
        wms_layers = root.findall('.//wms:Layer', namespaces) or root.findall('.//Layer', {})

        if not wms_layers:
            raise Exception('Keine Layer im WMS-Dienst gefunden')

        # Layer-Informationen sammeln
        for layer in wms_layers:
            name = layer.find('wms:Name', namespaces) or layer.find('Name')
            if name is None or not name.text:
                continue

            title = layer.find('wms:Title', namespaces) or layer.find('Title')
            abstract = layer.find('wms:Abstract', namespaces) or layer.find('Abstract')

            name_text = name.text
            title_text = title.text if title is not None else name_text
            abstract_text = abstract.text if abstract is not None else ''

            namespace = name_text.split(':')[0] if ':' in name_text else 'default'
            layer_name = name_text.split(':')[1] if ':' in name_text else name_text

            if namespace not in layers:
                layers[namespace] = {}

            layers[namespace][layer_name] = {
                'name': name_text,
                'title': title_text,
                'description': abstract_text,
                'attributes': []  # WMS hat keine Attribute
            }

        return layers

    def detect_state(url, root=None):
        """Erkennt das Bundesland aus der URL oder den Metadaten"""
        states = {
            'baden-wuerttemberg': ['bw', 'baden', 'wuerttemberg'],
            'bayern': ['by', 'bayern', 'bavarian'],
            'berlin': ['be', 'berlin'],
            'brandenburg': ['bb', 'brandenburg'],
            'bremen': ['hb', 'bremen'],
            'hamburg': ['hh', 'hamburg'],
            'hessen': ['he', 'hessen'],
            'mecklenburg-vorpommern': ['mv', 'mecklenburg', 'vorpommern'],
            'niedersachsen': ['ni', 'niedersachsen'],
            'nordrhein-westfalen': ['nw', 'nrw', 'nordrhein', 'westfalen'],
            'rheinland-pfalz': ['rp', 'rheinland', 'pfalz'],
            'saarland': ['sl', 'saar'],
            'sachsen': ['sn', 'sachsen', 'saxony'],
            'sachsen-anhalt': ['st', 'sachsen-anhalt'],
            'schleswig-holstein': ['sh', 'schleswig'],
            'thueringen': ['th', 'thueringen', 'thüringen']
        }
        
        url = url.lower()
        
        # Suche in URL
        for state, keywords in states.items():
            if any(kw in url for kw in keywords):
                return state
            
        # Suche in Metadaten falls vorhanden
        if root is not None:
            metadata_text = ET.tostring(root, encoding='unicode').lower()
            for state, keywords in states.items():
                if any(kw in metadata_text for kw in keywords):
                    return state
        
        return 'unknown'

    def extract_wfs_layer_info(feature_type, service_url, state):
        """Extrahiert Layer-Informationen aus WFS FeatureType"""
        try:
            name = feature_type.find('{http://www.opengis.net/wfs/2.0}Name')
            title = feature_type.find('{http://www.opengis.net/wfs/2.0}Title')
            abstract = feature_type.find('{http://www.opengis.net/wfs/2.0}Abstract')
            
            if name is None or not name.text:
                return None

            # Sammle Attribute
            attributes = []
            for elem in feature_type.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
                attr_name = elem.get('name')
                attr_type = elem.get('type', '').split(':')[-1]
                if attr_name:
                    attributes.append({
                        'name': attr_name,
                        'type': attr_type
                    })

            return {
                'name': name.text,
                'title': title.text if title is not None else name.text,
                'description': abstract.text if abstract is not None else '',
                'source_url': service_url,
                'source_type': 'WFS',
                'state': state,
                'attributes': attributes
            }
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren der WFS-Layer-Info: {str(e)}")
            return None

    def extract_wms_layer_info(layer, service_url, state):
        """Extrahiert Layer-Informationen aus WMS Layer"""
        try:
            name = layer.find('{http://www.opengis.net/wms}Name')
            title = layer.find('{http://www.opengis.net/wms}Title')
            abstract = layer.find('{http://www.opengis.net/wms}Abstract')
            
            if name is None or not name.text:
                return None

            return {
                'name': name.text,
                'title': title.text if title is not None else name.text,
                'description': abstract.text if abstract is not None else '',
                'source_url': service_url,
                'source_type': 'WMS',
                'state': state,
                'attributes': []  # WMS hat keine Attribute
            }
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren der WMS-Layer-Info: {str(e)}")
            return None

    def import_layer_batch(layer_batch):
        """Importiert einen Batch von Layern ins Lexikon"""
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        try:
            for layer in layer_batch:
                # KI-Verarbeitung der Layer-Informationen
                cleaned_name = ai_helper.clean_layer_name(layer['name'])
                ai_description = ai_helper.generate_layer_description(layer['name'], layer['description'])
                
                # Prüfe ob Layer bereits existiert
                cursor.execute('''
                    SELECT id FROM wfs_layers 
                    WHERE name = ? AND source_url = ?
                ''', (layer['name'], layer['source_url']))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existierenden Layer
                    cursor.execute('''
                        UPDATE wfs_layers 
                        SET title = ?,
                            description = ?,
                            cleaned_name = ?,
                            ai_description = ?,
                            state = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE name = ? AND source_url = ?
                    ''', (
                        layer['title'],
                        layer['description'],
                        cleaned_name,
                        ai_description,
                        layer['state'],
                        layer['name'],
                        layer['source_url']
                    ))
                else:
                    # Füge neuen Layer hinzu
                    cursor.execute('''
                        INSERT INTO wfs_layers (
                            name, title, description, 
                            cleaned_name, ai_description,
                            source_url, source_type, state,
                            created_at, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (
                        layer['name'],
                        layer['title'],
                        layer['description'],
                        cleaned_name,
                        ai_description,
                        layer['source_url'],
                        layer['source_type'],
                        layer['state']
                    ))
                
                layer_id = cursor.lastrowid if not existing else existing[0]
                
                # Füge Attribute hinzu
                for attr in layer['attributes']:
                    cursor.execute('''
                        INSERT INTO layer_attributes (
                            layer_id, name, type, description
                        ) VALUES (?, ?, ?, ?)
                    ''', (
                        layer_id,
                        attr['name'],
                        attr.get('type', ''),
                        attr.get('description', '')
                    ))
        
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        
        finally:
            conn.close()

    def init_data_lexicon():
        """Initialisiert die Datenbank für das Daten-Lexikon"""
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        try:
            # Erstelle Tabelle für Layer
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wfs_layers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cleaned_name TEXT,
                    title TEXT,
                    description TEXT,
                    ai_description TEXT,
                    source_url TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, source_url)
                )
            ''')
            
            # Füge neue Spalten hinzu, falls sie noch nicht existieren
            cursor.execute("PRAGMA table_info(wfs_layers)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'cleaned_name' not in columns:
                cursor.execute('ALTER TABLE wfs_layers ADD COLUMN cleaned_name TEXT')
            if 'ai_description' not in columns:
                cursor.execute('ALTER TABLE wfs_layers ADD COLUMN ai_description TEXT')

            # Erstelle Tabelle für Layer-Attribute
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS layer_attributes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT,
                    description TEXT,
                    FOREIGN KEY (layer_id) REFERENCES wfs_layers(id)
                )
            ''')
            
            # Erstelle Tabelle für Services
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    state TEXT,
                    status TEXT DEFAULT 'active',
                    last_checked TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url, type)
                )
            ''')
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        
        finally:
            conn.close()

    # Initialisiere Datenbank beim Start
    init_data_lexicon()

    @app.route('/debug_lexicon')
    def debug_lexicon():
        """Debug-Endpunkt für das Lexikon"""
        try:
            conn = sqlite3.connect(app.config['DATABASE'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    id, name, title, description, 
                    source_type, source_url, state,
                    created_at, last_updated
                FROM wfs_layers 
                ORDER BY created_at DESC
            ''')
            
            layers = cursor.fetchall()
            
            return jsonify({
                'layer_count': len(layers),
                'first_layer': layers[0] if layers else None,
                'columns': [
                    'id', 'name', 'title', 'description',
                    'source_type', 'source_url', 'state',
                    'created_at', 'last_updated'
                ]
            })
            
        except Exception as e:
            return jsonify({
                'error': str(e)
            })
        finally:
            if 'conn' in locals():
                conn.close()

    @app.route('/api/clean-layer-names', methods=['POST'])
    @auto_debug
    def clean_layer_names():
        """API-Endpunkt zum Säubern von Layer-Namen - Batch-Verarbeitung"""
        try:
            data = request.get_json()
            if not data or 'layers' not in data:
                return jsonify({
                    'status': 'error',
                    'error': 'Keine Layer zum Säubern gefunden'
                }), 400

            layers = data['layers']
            cleaned_layers = []
            batch_size = 10  # Maximale Batch-Größe
            
            # Verarbeite Layer in Batches
            for i in range(0, len(layers), batch_size):
                batch = layers[i:i + batch_size]
                
                try:
                    # Erstelle Liste der Layer-Namen für diesen Batch
                    layer_names = [layer['name'] for layer in batch]
                    layer_titles = [layer.get('title', '') for layer in batch]
                    
                    # Batch-Verarbeitung der Namen
                    cleaned_names = ai_helper.clean_layer_names_batch(layer_names)
                    descriptions = ai_helper.generate_layer_descriptions_batch(layer_names, layer_titles)
                    
                    # Füge die Ergebnisse zur Liste hinzu
                    for j, layer in enumerate(batch):
                        cleaned_layers.append({
                            'id': layer['name'],
                            'cleaned_name': cleaned_names[j] if j < len(cleaned_names) else layer['name'],
                            'explanation': descriptions[j] if j < len(descriptions) else "Keine Beschreibung verfügbar"
                        })
                        
                    logger.info(f"Batch von {len(batch)} Layern verarbeitet")
                    
                except Exception as e:
                    logger.error(f"Fehler bei der Batch-Verarbeitung: {str(e)}")
                    # Bei Fehler, füge unverarbeitete Layer hinzu
                    for layer in batch:
                        cleaned_layers.append({
                            'id': layer['name'],
                            'cleaned_name': layer['name'],
                            'explanation': f"Fehler bei der Verarbeitung: {str(e)}"
                        })

            return jsonify({
                'status': 'success',
                'cleaned_layers': cleaned_layers
            })

        except Exception as e:
            logger.error(f"Fehler bei der Layer-Säuberung: {str(e)}")
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    return app

if __name__ == '__main__':
    # Umgebung aus Umgebungsvariable oder Standard
    env = os.getenv('FLASK_ENV', 'default')
    app = create_app(env)
    
    # Server starten
    port = app.config['PORT']
    debug = app.config['DEBUG']
    
    print(f"Starting {env} server on port {port}")
    print(f"Debug mode: {debug}")
    print(f"Database: {app.config['DATABASE']}")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 