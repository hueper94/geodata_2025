import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import json
import os
import geopandas as gpd
from shapely.geometry import shape, Point, Polygon
from datetime import datetime
import psycopg2
import xmltodict
from owslib.wfs import WebFeatureService
import logging
from io import BytesIO
from shapely import make_valid
from owslib.wms import WebMapService
import numpy as np
from PIL import Image
import io
import zipfile
import tempfile
import shutil
from shapely.geometry import mapping

# Logger konfigurieren
logger = logging.getLogger(__name__)

class WFSExplorer:
    def __init__(self, url):
        """Initialisiert den WFS Explorer mit der angegebenen URL"""
        try:
            self.wfs = WebFeatureService(url, version='2.0.0', timeout=30)
            self.url = url
            self.layer_structure = self._get_layer_structure()
            self.supported_formats = self._get_supported_formats()
            self.metadata = self._get_metadata()
        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung des WFS: {str(e)}")
            raise

    def _get_layer_structure(self):
        """Extrahiert detaillierte Layer-Informationen aus dem WFS"""
        try:
            layers = {}
            for layer_name in self.wfs.contents:
                layer = self.wfs.contents[layer_name]
                namespace = layer_name.split(':')[0] if ':' in layer_name else 'default'
                
                if namespace not in layers:
                    layers[namespace] = {}
                
                # Metadaten-URLs extrahieren
                metadata_urls = []
                if hasattr(layer, 'metadataUrls'):
                    for m in layer.metadataUrls:
                        if isinstance(m, dict):
                            metadata_urls.append({
                                'url': m.get('url', ''),
                                'type': m.get('type', '')
                            })
                
                # Online-Ressourcen extrahieren
                online_resource = None
                if hasattr(layer, 'parent') and hasattr(layer.parent, 'provider'):
                    provider = layer.parent.provider
                    if hasattr(provider, 'url'):
                        online_resource = provider.url
                
                # Detaillierte Layer-Informationen sammeln
                layer_info = {
                    'title': layer.title or layer_name,
                    'abstract': layer.abstract or self._get_default_description(layer_name),
                    'bbox': layer.boundingBoxWGS84 if hasattr(layer, 'boundingBoxWGS84') else None,
                    'keywords': layer.keywords if hasattr(layer, 'keywords') else [],
                    'metadata_urls': metadata_urls,
                    'online_resource': online_resource,
                    'queryable': layer.queryable if hasattr(layer, 'queryable') else True
                }
                
                layers[namespace][layer_name] = layer_info
                
            return layers
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Layer-Struktur: {str(e)}")
            raise

    def _get_default_description(self, layer_name):
        """Generiert eine standardisierte Beschreibung basierend auf dem Layer-Namen"""
        try:
            parts = layer_name.split(':')
            if len(parts) > 1:
                theme = parts[0].lower()
                feature = parts[1]
                
                descriptions = {
                    'bfn': 'Naturschutzdaten vom Bundesamt für Naturschutz',
                    'wasser': 'Gewässerdaten aus dem Wasserinformationssystem',
                    'verkehr': 'Verkehrsinfrastrukturdaten',
                    'landwirtschaft': 'Landwirtschaftliche Flächendaten',
                    'schutzgebiet': 'Informationen zu Schutzgebieten',
                    'biotop': 'Biotopkartierung und -bewertung'
                }
                
                base_desc = descriptions.get(theme, 'Geodaten')
                return f"{base_desc} - {feature}"
            return "Keine Beschreibung verfügbar"
        except Exception:
            return "Keine Beschreibung verfügbar"

    def _get_provider_info(self):
        """Extrahiert Informationen über den Datenanbieter"""
        try:
            if hasattr(self.wfs, 'provider'):
                provider = self.wfs.provider
                return {
                    'name': provider.name if hasattr(provider, 'name') else None,
                    'url': provider.url if hasattr(provider, 'url') else None,
                    'contact': self._get_contact_info()
                }
            return None
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Provider-Informationen: {str(e)}")
            return None

    def _get_supported_formats(self):
        """Ermittelt die unterstützten Ausgabeformate"""
        try:
            formats = []
            operation = self.wfs.getOperationByName('GetFeature')
            if operation and 'outputFormat' in operation.parameters:
                formats = list(operation.parameters['outputFormat']['values'])
            return formats or ['application/json', 'GML3', 'SHAPE-ZIP']
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der unterstützten Formate: {str(e)}")
            return ['application/json', 'GML3', 'SHAPE-ZIP']

    def _get_metadata(self):
        """Extrahiert detaillierte Metadaten aus dem WFS"""
        try:
            metadata = {
                'title': self.wfs.identification.title,
                'abstract': self.wfs.identification.abstract,
                'keywords': self.wfs.identification.keywords,
                'provider': {
                    'name': self.wfs.provider.name if self.wfs.provider else None,
                    'url': self.wfs.provider.url if self.wfs.provider else None,
                    'contact': self._get_contact_info()
                },
                'version': self.wfs.version,
                'fees': self.wfs.identification.fees,
                'access_constraints': self.wfs.identification.accessconstraints
            }
            return metadata
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Metadaten: {str(e)}")
            return {}

    def _get_contact_info(self):
        """Extrahiert Kontaktinformationen aus dem WFS"""
        try:
            if not self.wfs.provider or not hasattr(self.wfs.provider, 'contact'):
                return {}
            
            contact = self.wfs.provider.contact
            return {
                'name': contact.name if hasattr(contact, 'name') else None,
                'organization': contact.organization if hasattr(contact, 'organization') else None,
                'position': contact.position if hasattr(contact, 'position') else None,
                'email': contact.email if hasattr(contact, 'email') else None,
                'phone': contact.phone if hasattr(contact, 'phone') else None
            }
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Kontaktinformationen: {str(e)}")
            return {}

    def get_preview_data(self, layer_name, bbox=None):
        """Lädt eine Vorschau der Daten und transformiert sie für die Webanzeige"""
        try:
            # WFS-Anfrage mit spezifischen Parametern
            params = {
                'typename': [layer_name],
                'outputFormat': 'application/json',
                'maxfeatures': 1000  # Erhöht für bessere Vorschau
            }
            
            if bbox:
                # Stelle sicher, dass die BBOX im richtigen Format ist
                if isinstance(bbox, str):
                    bbox = [float(x) for x in bbox.split(',')]
                params['bbox'] = bbox
            
            response = self.wfs.getfeature(**params)
            
            if hasattr(response, 'read'):
                data = response.read()
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                geojson_data = json.loads(data)
                
                # Transformiere die Geometrien falls nötig
                if 'features' in geojson_data:
                    for feature in geojson_data['features']:
                        if feature.get('geometry'):
                            # Validiere und repariere Geometrie falls nötig
                            geom = shape(feature['geometry'])
                            if not geom.is_valid:
                                geom = make_valid(geom)
                            # Stelle sicher, dass die Koordinaten im Web-Mercator-Format sind
                            feature['geometry'] = mapping(geom)
                
                return geojson_data
            return None
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Vorschau: {str(e)}")
            raise

    def download_and_convert(self, layer_name, output_format='GEOJSON', bbox=None):
        """Lädt Daten herunter und konvertiert sie in das gewünschte Format"""
        try:
            # Temporäres Verzeichnis erstellen
            temp_dir = tempfile.mkdtemp()
            
            # WFS-Anfrage mit spezifischen Parametern
            params = {
                'typename': [layer_name],
                'outputFormat': 'application/json'
            }
            
            if bbox:
                if isinstance(bbox, str):
                    bbox = [float(x) for x in bbox.split(',')]
                params['bbox'] = bbox
            
            response = self.wfs.getfeature(**params)
            
            # Response verarbeiten
            if hasattr(response, 'read'):
                data = response.read()
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                geojson_data = json.loads(data)
            else:
                geojson_data = response
            
            # Dateinamen vorbereiten
            output_filename = f"{layer_name.replace(':', '_')}"
            
            if output_format.upper() == 'GEOJSON':
                # GeoJSON direkt speichern
                output_path = os.path.join(temp_dir, f"{output_filename}.geojson")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(geojson_data, f)
                
            elif output_format.upper() in ['SHAPEFILE', 'GPKG']:
                # GeoJSON in GeoDataFrame konvertieren
                gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])
                
                # CRS setzen falls nicht vorhanden
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                
                # Geometrien validieren und reparieren
                gdf['geometry'] = gdf['geometry'].apply(lambda geom: make_valid(geom) if not geom.is_valid else geom)
                
                if output_format.upper() == 'SHAPEFILE':
                    # Shapefile erstellen
                    output_path = os.path.join(temp_dir, f"{output_filename}.shp")
                    gdf.to_file(output_path, driver='ESRI Shapefile', encoding='utf-8')
                    
                    # ZIP-Datei erstellen
                    zip_path = os.path.join(temp_dir, f"{output_filename}_shp.zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                            file_path = os.path.join(temp_dir, f"{output_filename}{ext}")
                            if os.path.exists(file_path):
                                zipf.write(file_path, os.path.basename(file_path))
                    output_path = zip_path
                    
                else:  # GPKG
                    output_path = os.path.join(temp_dir, f"{output_filename}.gpkg")
                    gdf.to_file(output_path, driver='GPKG')
            
            return output_path
            
        except Exception as e:
            logger.error(f"Fehler beim Download und Konvertierung: {str(e)}")
            raise
        finally:
            # Temporäres Verzeichnis aufräumen
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def get_capabilities_info(self):
        """Gibt detaillierte Informationen über den WFS-Dienst zurück"""
        return {
            'identification': {
                'title': self.wfs.identification.title,
                'abstract': self.wfs.identification.abstract,
                'keywords': self.wfs.identification.keywords,
                'accessconstraints': self.wfs.identification.accessconstraints,
                'fees': self.wfs.identification.fees
            },
            'provider': {
                'name': self.wfs.provider.name if self.wfs.provider else None,
                'url': self.wfs.provider.url if self.wfs.provider else None,
                'contact': self._get_contact_info()
            },
            'operations': list(self.wfs.operations),
            'contents': self.layer_structure
        }

    def download_by_bbox(self, layer_name, bbox, output_format='GML'):
        """
        Lädt Daten für einen bestimmten Bereich herunter
        """
        return self.download_and_convert(layer_name, output_format, bbox)
        
    def download_all_layers(self, output_format='GML'):
        """
        Lädt alle verfügbaren Layer herunter
        """
        results = []
        for namespace, layers in self.layer_structure.items():
            if isinstance(layers, dict):
                for layer_name in layers.keys():
                    full_layer_name = f"{namespace}:{layer_name}"
                    result = self.download_and_convert(full_layer_name, output_format)
                    if result:
                        results.append(result)
        return results

    def print_layer_structure(self, structure=None, indent=0):
        """Gibt die Layer-Struktur übersichtlich aus"""
        if structure is None:
            structure = self.layer_structure
        
        for namespace, layers in structure.items():
            print("  " * indent + f"Namespace: {namespace}")
            if isinstance(layers, dict):
                for layer_name, info in layers.items():
                    print("  " * (indent + 1) + f"Layer: {layer_name}")
                    print("  " * (indent + 2) + f"Titel: {info['title']}")
                    if info['abstract']:
                        print("  " * (indent + 2) + f"Beschreibung: {info['abstract']}")
                    print("  " * (indent + 2) + f"CRS: {', '.join(info['crs'])}")
                    if info['bbox']:
                        print("  " * (indent + 2) + "Bounding Box:")
                        print("  " * (indent + 3) + f"Südwest: {info['bbox']['lower']}")
                        print("  " * (indent + 3) + f"Nordost: {info['bbox']['upper']}")
                    print("  " * (indent + 2) + "Attribute:")
                    for attr in info['attributes']:
                        print("  " * (indent + 3) + f"{attr['name']}: {attr['type']}")
                    print()

    def extract_geometries_from_wms(self, url, layer_name, bbox, width=1000, height=1000, sample_points=100):
        """
        Extrahiert Geometrien aus einem WMS-Layer durch systematische GetFeatureInfo-Anfragen
        
        Args:
            url: WMS Service URL
            layer_name: Name des Layers
            bbox: Bounding Box [minx, miny, maxx, maxy]
            width: Bildbreite für WMS-Anfrage
            height: Bildhöhe für WMS-Anfrage
            sample_points: Anzahl der Stichprobenpunkte
        
        Returns:
            GeoJSON FeatureCollection mit extrahierten Geometrien
        """
        try:
            # WMS-Service initialisieren
            wms = WebMapService(url)
            
            # GetMap-Anfrage für Basisbild
            img = wms.getmap(
                layers=[layer_name],
                srs='EPSG:4326',
                bbox=bbox,
                size=(width, height),
                format='image/png',
                transparent=True
            )
            
            # Bild in numpy-Array konvertieren
            image = Image.open(io.BytesIO(img.read()))
            img_array = np.array(image)
            
            # Punktgitter erstellen
            x = np.linspace(bbox[0], bbox[2], int(np.sqrt(sample_points)))
            y = np.linspace(bbox[1], bbox[3], int(np.sqrt(sample_points)))
            points = []
            
            for i in x:
                for j in y:
                    # GetFeatureInfo für jeden Punkt
                    feature_info = wms.getfeatureinfo(
                        layers=[layer_name],
                        srs='EPSG:4326',
                        bbox=bbox,
                        size=(width, height),
                        format='image/png',
                        query_layers=[layer_name],
                        info_format='application/json',
                        xy=(int((i-bbox[0])/(bbox[2]-bbox[0])*width),
                            int((j-bbox[1])/(bbox[3]-bbox[1])*height))
                    )
                    
                    try:
                        info = json.loads(feature_info.read().decode('utf-8'))
                        if info.get('features'):
                            for feature in info['features']:
                                if feature.get('geometry'):
                                    points.append(Point(i, j))
                    except:
                        continue
            
            # Punktwolke in Polygone konvertieren
            if points:
                # Convex Hull oder Concave Hull je nach Bedarf
                from shapely.ops import unary_union
                hull = unary_union(points).convex_hull
                
                return {
                    'type': 'FeatureCollection',
                    'features': [{
                        'type': 'Feature',
                        'geometry': mapping(hull),
                        'properties': {
                            'source': 'WMS',
                            'layer': layer_name,
                            'extraction_method': 'GetFeatureInfo'
                        }
                    }]
                }
            
            return {
                'type': 'FeatureCollection',
                'features': []
            }
            
        except Exception as e:
            logger.error(f"Fehler bei der WMS-Geometrie-Extraktion: {str(e)}")
            return {
                'type': 'FeatureCollection',
                'features': []
            }

    def extract_geometries_from_wms_image(self, url, layer_name, bbox, width=1000, height=1000):
        """
        Extrahiert Geometrien aus einem WMS-Layer durch Bildanalyse
        
        Args:
            url: WMS Service URL
            layer_name: Name des Layers
            bbox: Bounding Box [minx, miny, maxx, maxy]
            width: Bildbreite
            height: Bildhöhe
        
        Returns:
            GeoJSON FeatureCollection mit extrahierten Geometrien
        """
        try:
            # WMS-Service initialisieren
            wms = WebMapService(url)
            
            # GetMap-Anfrage
            img = wms.getmap(
                layers=[layer_name],
                srs='EPSG:4326',
                bbox=bbox,
                size=(width, height),
                format='image/png',
                transparent=True
            )
            
            # Bild in numpy-Array konvertieren
            image = Image.open(io.BytesIO(img.read()))
            img_array = np.array(image)
            
            # Alpha-Kanal extrahieren (falls vorhanden)
            if img_array.shape[-1] == 4:
                alpha = img_array[:, :, 3]
            else:
                # Graustufenbild erstellen
                image = image.convert('L')
                alpha = np.array(image)
            
            # Binäre Maske erstellen
            mask = alpha > 0
            
            # Konturen finden
            from skimage import measure
            contours = measure.find_contours(mask.astype(float), 0.5)
            
            features = []
            for contour in contours:
                # Koordinaten in Geo-Koordinaten umwandeln
                geo_coords = []
                for point in contour:
                    y, x = point
                    geo_x = bbox[0] + (x / width) * (bbox[2] - bbox[0])
                    geo_y = bbox[1] + (y / height) * (bbox[3] - bbox[1])
                    geo_coords.append((geo_x, geo_y))
                
                # Polygon erstellen
                if len(geo_coords) > 2:
                    # Polygon schließen
                    if geo_coords[0] != geo_coords[-1]:
                        geo_coords.append(geo_coords[0])
                    
                    poly = Polygon(geo_coords)
                    if poly.is_valid:
                        features.append({
                            'type': 'Feature',
                            'geometry': mapping(poly),
                            'properties': {
                                'source': 'WMS',
                                'layer': layer_name,
                                'extraction_method': 'ImageAnalysis'
                            }
                        })
            
            return {
                'type': 'FeatureCollection',
                'features': features
            }
            
        except Exception as e:
            logger.error(f"Fehler bei der WMS-Bildanalyse: {str(e)}")
            return {
                'type': 'FeatureCollection',
                'features': []
            }

    def get_layer_details(self, layer_name):
        """Ruft detaillierte Informationen für einen spezifischen Layer ab"""
        try:
            if layer_name in self.wfs.contents:
                layer = self.wfs.contents[layer_name]
                
                # Versuche zusätzliche Metadaten abzurufen
                metadata = {}
                if hasattr(layer, 'metadataUrls'):
                    for url_info in layer.metadataUrls:
                        try:
                            if isinstance(url_info, dict) and 'url' in url_info:
                                response = requests.get(url_info['url'], timeout=5)
                                if response.status_code == 200:
                                    metadata = xmltodict.parse(response.text)
                        except Exception as e:
                            logger.warning(f"Fehler beim Abrufen der Metadaten: {str(e)}")
                
                return {
                    'title': layer.title or layer_name,
                    'abstract': layer.abstract or self._get_default_description(layer_name),
                    'keywords': layer.keywords if hasattr(layer, 'keywords') else [],
                    'bbox': layer.boundingBoxWGS84 if hasattr(layer, 'boundingBoxWGS84') else None,
                    'metadata': metadata,
                    'provider': self._get_provider_info()
                }
            return None
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Layer-Details: {str(e)}")
            return None

    def get_layer_descriptions(self):
        """Gibt detaillierte Beschreibungen für jeden Layer zurück"""
        descriptions = {
            'bfn:Naturschutzgebiete': {
                'description': 'Naturschutzgebiete sind rechtsverbindlich festgesetzte Gebiete, in denen ein besonderer Schutz von Natur und Landschaft erforderlich ist. Sie dienen der Erhaltung, Entwicklung oder Wiederherstellung von Biotopen und Lebensgemeinschaften.',
                'link': 'https://www.bfn.de/naturschutzgebiete',
                'source': 'Bundesamt für Naturschutz'
            },
            'bfn:Nationalparke': {
                'description': 'Nationalparke sind großräumige Schutzgebiete, die sich in einem überwiegend unbeeinflussten Zustand befinden. Sie sollen großräumig den möglichst ungestörten Ablauf der Naturvorgänge in ihrer natürlichen Dynamik gewährleisten.',
                'link': 'https://www.bfn.de/nationalparke',
                'source': 'Bundesamt für Naturschutz'
            },
            'bfn:Biosphaerenreservate': {
                'description': 'Biosphärenreservate sind großflächige Kulturlandschaften mit reicher Naturausstattung. Sie dienen der Entwicklung und Erprobung nachhaltiger Wirtschaftsweisen und dem Erhalt der biologischen Vielfalt.',
                'link': 'https://www.bfn.de/biosphaerenreservate',
                'source': 'Bundesamt für Naturschutz'
            },
            'wasser:Gewaesser': {
                'description': 'Umfassende Darstellung der Gewässer und Wasserstraßen in Deutschland. Die Daten beinhalten Informationen über Fließgewässer, stehende Gewässer und künstliche Wasserstraßen.',
                'link': 'https://www.wasserblick.net',
                'source': 'Wasserblick - Bund/Länder-Informationsportal'
            },
            'verkehr:Strassen': {
                'description': 'Detaillierte Darstellung des Straßennetzes einschließlich Autobahnen, Bundesstraßen und wichtiger Verkehrsknotenpunkte. Die Daten werden regelmäßig aktualisiert.',
                'link': 'https://www.bast.de',
                'source': 'Bundesanstalt für Straßenwesen'
            },
            'landwirtschaft:Agrarflaechen': {
                'description': 'Kartierung der landwirtschaftlich genutzten Flächen in Deutschland. Enthält Informationen über Anbauflächen, Grünland und landwirtschaftliche Nutzungsarten.',
                'link': 'https://www.landwirtschaft.de',
                'source': 'Bundesministerium für Ernährung und Landwirtschaft'
            }
        }
        return descriptions

    def print_layer_descriptions(self):
        """Zeigt formatierte Beschreibungen für alle Layer an"""
        descriptions = self.get_layer_descriptions()
        print("\n=== Layer-Beschreibungen ===\n")
        for layer_name, info in descriptions.items():
            print(f"Layer: {layer_name}")
            print(f"Beschreibung: {info['description']}")
            print(f"Weitere Informationen: {info['link']}")
            print(f"Quelle: {info['source']}\n")

# Beispiel für die Verwendung
if __name__ == "__main__":
    # BfN WFS-URL
    wfs_url = "https://geodienste.bfn.de/ogc/wfs/schutzgebiet"
    
    explorer = WFSExplorer(wfs_url)
    
    # Unterstützte Formate anzeigen
    print("=== Unterstützte Formate ===")
    print('\n'.join(explorer.supported_formats))
    print()
    
    # Layer-Struktur anzeigen
    print("=== WFS Layer-Struktur ===")
    explorer.print_layer_structure()
    
    # Beispiel 1: Einzelnen Layer herunterladen
    layer_name = "bfn_sch_Schutzgebiet:Nationalparke"
    explorer.download_and_convert(layer_name, output_format='GEOJSON')
    
    # Beispiel 2: Layer mit BBOX herunterladen (z.B. für Berlin)
    bbox = [13.088333, 52.338167, 13.761667, 52.675833]
    explorer.download_by_bbox(layer_name, bbox, output_format='GPKG')
    
    # Beispiel 3: Alle Layer herunterladen
    explorer.download_all_layers(output_format='SHAPEFILE') 