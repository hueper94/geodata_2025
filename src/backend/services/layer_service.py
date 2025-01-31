import logging
from owslib.wfs import WebFeatureService
import requests
import xml.etree.ElementTree as ET
import urllib3
from threading import Lock
from .qgis_service import QgisService

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class LayerStatus:
    LOADING = 'loading'
    READY = 'ready'
    ERROR = 'error'

class LayerService:
    def __init__(self):
        self.WFS_VERSIONS = ['2.0.0', '1.1.0', '1.0.0']
        self.qgis_service = QgisService()
        self.layer_cache = {}
        self.layer_cache_lock = Lock()

    def test_wfs_version(self, url, version):
        """Testet, ob ein WFS-Dienst mit einer bestimmten Version funktioniert"""
        logger.info(f"Teste WFS Version {version} für URL: {url}")
        try:
            params = {
                'service': 'WFS',
                'version': version,
                'request': 'GetCapabilities'
            }
            logger.info(f"Sende GetCapabilities Anfrage mit Parametern: {params}")
            response = requests.get(url, params=params, timeout=10, verify=False)
            logger.info(f"Server Antwort Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.content)
                    logger.info(f"XML erfolgreich geparst, Root-Tag: {root.tag}")
                    
                    # Suche nach Feature Types mit verschiedenen XPath-Ausdrücken
                    feature_types = root.find('.//FeatureType')
                    feature_types_2 = root.find('.//{http://www.opengis.net/wfs/2.0}FeatureType')
                    
                    logger.info(f"Feature Types gefunden: Standard={feature_types is not None}, WFS2.0={feature_types_2 is not None}")
                    
                    if feature_types is not None or feature_types_2 is not None:
                        logger.info(f"WFS Version {version} erfolgreich getestet für {url}")
                        return True
                except ET.ParseError as e:
                    logger.error(f"XML Parse Error: {str(e)}")
                    pass
            return False
        except Exception as e:
            logger.error(f"Fehler beim Testen von WFS Version {version}: {str(e)}")
            return False

    def get_working_wfs_version(self, url):
        """Findet die funktionierende WFS-Version für einen Dienst"""
        logger.info(f"Suche funktionierende WFS-Version für URL: {url}")
        for version in self.WFS_VERSIONS:
            if self.test_wfs_version(url, version):
                logger.info(f"Funktionierende Version gefunden: {version}")
                return version
        logger.error("Keine funktionierende WFS-Version gefunden")
        return None

    def get_layers(self, wfs_url):
        """Ruft die verfügbaren Layer von einem WFS-Dienst ab"""
        logger.info(f"Starte Layer-Abruf für URL: {wfs_url}")
        try:
            # Teste verschiedene WFS-Versionen
            version = self.get_working_wfs_version(wfs_url)
            if not version:
                raise ValueError('Keine kompatible WFS-Version gefunden')

            logger.info(f"Initialisiere WFS-Verbindung mit Version {version}")
            # Initialisiere WFS-Verbindung
            wfs = WebFeatureService(url=wfs_url, version=version, timeout=30)
            
            # Extrahiere Layer-Informationen
            layers = {}
            logger.info(f"Gefundene Layer: {len(wfs.contents)}")
            
            for layer_name, layer_info in wfs.contents.items():
                namespace = layer_info.id.split(':')[0] if ':' in layer_info.id else 'default'
                logger.info(f"Verarbeite Layer: {layer_name} (Namespace: {namespace})")
                
                if namespace not in layers:
                    layers[namespace] = {}
                
                layers[namespace][layer_name] = {
                    'name': layer_name,
                    'title': layer_info.title,
                    'abstract': layer_info.abstract,
                    'bbox': layer_info.boundingBoxWGS84,
                    'crs': layer_info.crsOptions[0] if layer_info.crsOptions else None,
                    'output_formats': layer_info.outputFormats
                }
                
                # Speichere Layer-Status im Cache
                with self.layer_cache_lock:
                    self.layer_cache[layer_name] = LayerStatus.READY
            
            logger.info(f"Layer-Abruf abgeschlossen. {len(layers)} Namespaces gefunden.")
            return {
                'status': 'success',
                'wfs_url': wfs_url,
                'version': version,
                'layers': layers
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Layer: {str(e)}")
            raise

    def get_layer_status(self, layer_name):
        """Gibt den Status eines Layers zurück"""
        with self.layer_cache_lock:
            return self.layer_cache.get(layer_name, LayerStatus.ERROR)

    def set_layer_status(self, layer_name, status):
        """Setzt den Status eines Layers"""
        with self.layer_cache_lock:
            self.layer_cache[layer_name] = status 