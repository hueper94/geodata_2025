from owslib.wfs import WebFeatureService

# WFS-Service verbinden
wfs = WebFeatureService(
    url="https://www.wfs.nrw.de/geobasis/wfs_nw_inspire-adressen",
    version="2.0.0"
)

# Verfügbare Layer anzeigen
print("Verfügbare Layer:")
for layer in list(wfs.contents):
    print(f"- {layer}")
    
# Details zum ersten Layer anzeigen
if wfs.contents:
    first_layer = list(wfs.contents)[0]
    layer_info = wfs.contents[first_layer]
    print(f"\nDetails zum Layer '{first_layer}':")
    print(f"Titel: {layer_info.title}")
    print(f"Abstrakt: {layer_info.abstract}")
    print(f"Bounding Box: {layer_info.boundingBoxWGS84}")
    print(f"CRS: {layer_info.crsOptions}")
    print(f"Ausgabeformate: {layer_info.outputFormats}") 