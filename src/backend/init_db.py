import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialisiert die SQLite Datenbank mit den benötigten Tabellen"""
    try:
        # Stelle sicher, dass das Verzeichnis existiert
        os.makedirs('src/backend', exist_ok=True)
        
        # Verbindung zur Datenbank herstellen
        conn = sqlite3.connect('src/backend/database.db')
        c = conn.cursor()
        
        # WFS Layer Tabelle
        c.execute('''
            CREATE TABLE IF NOT EXISTS wfs_layers (
                name TEXT PRIMARY KEY,
                title TEXT,
                translated_title TEXT,
                type TEXT,
                source_url TEXT,
                attributes TEXT,
                discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Attribut Übersetzungen Tabelle
        c.execute('''
            CREATE TABLE IF NOT EXISTS attribute_translations (
                layer_name TEXT,
                attribute_name TEXT,
                original_value TEXT,
                translated_value TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (layer_name, attribute_name, original_value)
            )
        ''')
        
        # Änderungen speichern
        conn.commit()
        logger.info("Datenbank erfolgreich initialisiert")
        
    except Exception as e:
        logger.error(f"Fehler bei der Datenbankinitialisierung: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    init_db() 