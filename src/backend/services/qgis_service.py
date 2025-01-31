import os
import time
import logging
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import QThread

logger = logging.getLogger(__name__)

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

class QgisService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QgisService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # QGIS Umgebungsvariablen setzen
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        os.environ['QGIS_PREFIX_PATH'] = '/usr'
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/usr/lib/x86_64-linux-gnu/qt5/plugins'
        
        # QGIS in separatem Thread starten
        logger.info("Starte QGIS-Thread...")
        self.qgis_thread = QgisThread()
        self.qgis_thread.start()
        time.sleep(2)  # Warte bis QGIS initialisiert ist
        
        # Projekt initialisieren
        self.project = QgsProject.instance()
        logger.info(f"QGIS-Projekt initialisiert - CRS: {self.project.crs().authid()}")
        
        self._initialized = True
    
    def get_project(self):
        return self.project
    
    def create_vector_layer(self, uri, name, provider='WFS'):
        """Erstellt einen neuen Vector Layer"""
        layer = QgsVectorLayer(uri, name, provider)
        if not layer.isValid():
            raise ValueError(f"Layer konnte nicht erstellt werden: {name}")
        return layer
    
    def add_layer_to_project(self, layer):
        """Fügt einen Layer zum Projekt hinzu"""
        return self.project.addMapLayer(layer)
    
    def remove_layer_from_project(self, layer_id):
        """Entfernt einen Layer aus dem Projekt"""
        self.project.removeMapLayer(layer_id) 