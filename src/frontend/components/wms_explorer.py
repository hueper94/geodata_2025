import logging
from owslib.wms import WebMapService
import numpy as np
from PIL import Image
import io
import json
from shapely.geometry import Point, Polygon, mapping
from shapely import make_valid
from shapely.ops import unary_union
from skimage import measure

# Logger konfigurieren
logger = logging.getLogger(__name__)

class WMSExplorer:
    def __init__(self, url):
        self.url = url
        self.wms = WebMapService(url)
        self.layers = self._get_layers()

    def _get_layers(self):
        """Verfügbare Layer abrufen"""
        return list(self.wms.contents)

    def extract_geometries_from_wms(self, layer_name, bbox, width=1000, height=1000, sample_points=100):
        """
        Extrahiert Geometrien aus einem WMS-Layer durch systematische GetFeatureInfo-Anfragen
        
        Args:
            layer_name: Name des Layers
            bbox: Bounding Box [minx, miny, maxx, maxy]
            width: Bildbreite für WMS-Anfrage
            height: Bildhöhe für WMS-Anfrage
            sample_points: Anzahl der Stichprobenpunkte
        
        Returns:
            GeoJSON FeatureCollection mit extrahierten Geometrien
        """
        try:
            logger.info(f"Starte GetFeatureInfo-basierte Extraktion für Layer {layer_name}")
            
            # GetMap-Anfrage für Basisbild
            img = self.wms.getmap(
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
            
            # Unterstützte Info-Formate ermitteln
            info_formats = ['application/json', 'application/vnd.ogc.gml', 'text/xml', 'text/plain']
            
            for i in x:
                for j in y:
                    # Versuche verschiedene Info-Formate
                    for info_format in info_formats:
                        try:
                            feature_info = self.wms.getfeatureinfo(
                                layers=[layer_name],
                                srs='EPSG:4326',
                                bbox=bbox,
                                size=(width, height),
                                format='image/png',
                                query_layers=[layer_name],
                                info_format=info_format,
                                xy=(int((i-bbox[0])/(bbox[2]-bbox[0])*width),
                                    int((j-bbox[1])/(bbox[3]-bbox[1])*height))
                            )
                            
                            content = feature_info.read()
                            if not content:
                                continue
                                
                            # Versuche den Inhalt zu parsen
                            if info_format == 'application/json':
                                info = json.loads(content.decode('utf-8'))
                                if info.get('features'):
                                    for feature in info['features']:
                                        if feature.get('geometry'):
                                            points.append(Point(i, j))
                                    break
                            elif 'xml' in info_format or 'gml' in info_format:
                                # XML/GML Parsing hier implementieren wenn nötig
                                if b'<' in content and b'>' in content:
                                    points.append(Point(i, j))
                                    break
                            else:
                                # Text-Format
                                if len(content.strip()) > 0:
                                    points.append(Point(i, j))
                                    break
                                    
                        except Exception as e:
                            logger.debug(f"Fehler bei Format {info_format}: {str(e)}")
                            continue
            
            # Punktwolke in Polygone konvertieren
            if points:
                hull = unary_union(points).convex_hull
                
                return {
                    'type': 'FeatureCollection',
                    'features': [{
                        'type': 'Feature',
                        'geometry': mapping(hull),
                        'properties': {
                            'source': 'WMS',
                            'layer': layer_name,
                            'extraction_method': 'GetFeatureInfo',
                            'point_count': len(points)
                        }
                    }]
                }
            
            logger.warning("Keine Features gefunden")
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

    def extract_geometries_from_wms_image(self, layer_name, bbox, width=1000, height=1000):
        """
        Extrahiert Geometrien aus einem WMS-Layer durch Bildanalyse
        
        Args:
            layer_name: Name des Layers
            bbox: Bounding Box [minx, miny, maxx, maxy]
            width: Bildbreite
            height: Bildhöhe
        
        Returns:
            GeoJSON FeatureCollection mit extrahierten Geometrien
        """
        try:
            logger.info(f"Starte Bildanalyse-basierte Extraktion für Layer {layer_name}")
            
            # GetMap-Anfrage
            img = self.wms.getmap(
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
                    
                    try:
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
                    except Exception as e:
                        logger.warning(f"Fehler beim Erstellen des Polygons: {str(e)}")
                        continue
            
            if not features:
                logger.warning("Keine Features gefunden")
            else:
                logger.info(f"{len(features)} Features extrahiert")
            
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

    def get_layer_info(self, layer_name):
        """Layer-Informationen abrufen"""
        if layer_name in self.wms.contents:
            layer = self.wms.contents[layer_name]
            return {
                'title': layer.title,
                'abstract': layer.abstract,
                'bbox': layer.boundingBox,
                'crs': layer.crsOptions,
                'styles': list(layer.styles.keys()) if hasattr(layer, 'styles') else []
            }
        return None 