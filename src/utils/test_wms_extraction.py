from wms_explorer import WMSExplorer
import json
import logging

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_wms_extraction():
    # WMS-URL für OpenStreetMap WMS
    wms_url = "https://ows.terrestris.de/osm/service"
    
    # Layer-Name
    layer_name = "OSM-WMS"
    
    # Bounding Box für einen kleinen Bereich (z.B. Zentrum von Düsseldorf)
    bbox = [6.773, 51.220, 6.783, 51.230]
    
    # WMSExplorer instanziieren
    explorer = WMSExplorer(wms_url)
    
    # Verfügbare Layer anzeigen
    logger.info("Verfügbare Layer:")
    for layer in explorer.layers:
        info = explorer.get_layer_info(layer)
        logger.info(f"- {layer}: {info['title']}")
    
    logger.info("\nStarte Geometrie-Extraktion aus WMS...")
    
    # Methode 1: GetFeatureInfo
    logger.info("Methode 1: GetFeatureInfo-basierte Extraktion")
    geometries1 = explorer.extract_geometries_from_wms(
        layer_name, 
        bbox,
        width=1000,
        height=1000,
        sample_points=100
    )
    
    # Ergebnisse speichern
    with open('wms_geometries_method1.geojson', 'w', encoding='utf-8') as f:
        json.dump(geometries1, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Methode 1: {len(geometries1['features'])} Features extrahiert")
    
    # Methode 2: Bildanalyse
    logger.info("Methode 2: Bildanalyse-basierte Extraktion")
    geometries2 = explorer.extract_geometries_from_wms_image(
        layer_name,
        bbox,
        width=1000,
        height=1000
    )
    
    # Ergebnisse speichern
    with open('wms_geometries_method2.geojson', 'w', encoding='utf-8') as f:
        json.dump(geometries2, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Methode 2: {len(geometries2['features'])} Features extrahiert")

if __name__ == "__main__":
    test_wms_extraction() 