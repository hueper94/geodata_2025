import os
import shutil
import json
import datetime
import logging
import ast
import zipfile
from pathlib import Path
import geopandas as gpd
from typing import Dict, List, Set, Tuple
import git
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import schedule
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import pylint.lint
from pylint.reporters import JSONReporter
import io

class AutoOrganizer:
    def __init__(self, base_dir: str, cloud_config: Dict = None):
        self.base_dir = Path(base_dir)
        self.cloud_config = cloud_config or {}
        self.setup_logging()
        self.create_directory_structure()
        self.setup_git()
        
    def setup_logging(self):
        """Konfiguriert das Logging-System"""
        log_dir = self.base_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'auto_organizer.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def create_directory_structure(self):
        """Erstellt die grundlegende Verzeichnisstruktur"""
        directories = [
            'src',
            'data/raw',
            'data/processed',
            'logs',
            'backups',
            'data/corrupted'  # Neuer Ordner für beschädigte Dateien
        ]
        
        for dir_path in directories:
            (self.base_dir / dir_path).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Verzeichnis erstellt: {dir_path}")
            
    def setup_git(self):
        """Initialisiert Git-Repository falls noch nicht vorhanden"""
        try:
            self.repo = git.Repo(self.base_dir)
        except git.exc.InvalidGitRepositoryError:
            self.repo = git.Repo.init(self.base_dir)
            self.logger.info("Git-Repository initialisiert")
            
    def git_commit(self, message: str):
        """Erstellt einen Git-Commit mit den aktuellen Änderungen"""
        try:
            if self.repo.is_dirty(untracked_files=True):
                self.repo.git.add(A=True)
                self.repo.index.commit(message)
                self.logger.info(f"Git-Commit erstellt: {message}")
        except Exception as e:
            self.logger.error(f"Fehler beim Git-Commit: {str(e)}")
            
    def analyze_code_quality(self, file_path: Path) -> Dict:
        """Analysiert die Code-Qualität mit Pylint"""
        if file_path.suffix.lower() != '.py':
            return {}
            
        output = io.StringIO()
        reporter = JSONReporter(output)
        
        try:
            pylint.lint.Run(
                [str(file_path)],
                reporter=reporter,
                do_exit=False
            )
            
            results = json.loads(output.getvalue())
            
            # Extrahiere wichtige Metriken
            metrics = {
                'code_quality_score': results.get('score', 0),
                'issues': [
                    {
                        'type': issue['type'],
                        'message': issue['message'],
                        'line': issue['line']
                    }
                    for issue in results.get('messages', [])
                ]
            }
            
            return metrics
        except Exception as e:
            self.logger.error(f"Fehler bei der Code-Qualitätsanalyse: {str(e)}")
            return {}
            
    def upload_to_cloud(self, file_path: Path):
        """Lädt eine Datei in den konfigurierten Cloud-Dienst hoch"""
        if not self.cloud_config:
            return
            
        try:
            if self.cloud_config['type'] == 'nextcloud':
                self._upload_to_nextcloud(file_path)
            elif self.cloud_config['type'] == 'gdrive':
                self._upload_to_gdrive(file_path)
        except Exception as e:
            self.logger.error(f"Fehler beim Cloud-Upload: {str(e)}")
            
    def _upload_to_nextcloud(self, file_path: Path):
        """Lädt eine Datei zu Nextcloud hoch"""
        url = f"{self.cloud_config['url']}/remote.php/dav/files/{self.cloud_config['user']}"
        auth = (self.cloud_config['user'], self.cloud_config['password'])
        
        with open(file_path, 'rb') as f:
            response = requests.put(
                f"{url}/{file_path.name}",
                data=f,
                auth=auth
            )
            
        if response.status_code in [200, 201, 204]:
            self.logger.info(f"Datei erfolgreich zu Nextcloud hochgeladen: {file_path.name}")
        else:
            self.logger.error(f"Fehler beim Nextcloud-Upload: {response.status_code}")
            
    def optimize_code(self, file_path: Path) -> List[str]:
        """Analysiert Code und schlägt Optimierungen vor"""
        if file_path.suffix.lower() != '.py':
            return []
            
        suggestions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            # Suche nach häufigen Anti-Patterns
            for node in ast.walk(tree):
                # Lange Funktionen
                if isinstance(node, ast.FunctionDef) and len(node.body) > 20:
                    suggestions.append(f"Funktion '{node.name}' ist sehr lang. Erwägen Sie eine Aufteilung in kleinere Funktionen.")
                
                # Verschachtelte Schleifen
                if isinstance(node, (ast.For, ast.While)):
                    for child in ast.walk(node):
                        if isinstance(child, (ast.For, ast.While)) and child != node:
                            suggestions.append("Verschachtelte Schleifen gefunden. Prüfen Sie, ob diese optimiert werden können.")
                            break
                
                # Viele lokale Variablen
                if isinstance(node, ast.FunctionDef):
                    locals_count = len([n for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)])
                    if locals_count > 15:
                        suggestions.append(f"Funktion '{node.name}' hat viele lokale Variablen ({locals_count}). Erwägen Sie eine Umstrukturierung.")
                        
            return suggestions
        except Exception as e:
            self.logger.error(f"Fehler bei der Code-Optimierung: {str(e)}")
            return []

    def schedule_tasks(self):
        """Richtet zeitgesteuerte Aufgaben ein"""
        # Tägliche Aufgaben
        schedule.every().day.at("00:00").do(self.run)
        
        # Wöchentliches Backup
        schedule.every().monday.at("01:00").do(self.create_backup)
        
        # Stündliche Git-Commits
        schedule.every().hour.do(lambda: self.git_commit("Automatischer stündlicher Commit"))
        
        while True:
            schedule.run_pending()
            time.sleep(60)

    def analyze_files(self) -> Dict:
        """Analysiert alle Dateien im Basis-Verzeichnis"""
        file_info = {}
        
        for file_path in self.base_dir.rglob('*'):
            if file_path.is_file():
                try:
                    info = self.get_file_info(file_path)
                    file_info[str(file_path)] = info
                except Exception as e:
                    self.logger.error(f"Fehler bei der Analyse von {file_path}: {str(e)}")
                    
        return file_info
    
    def get_file_info(self, file_path: Path) -> Dict:
        """Sammelt Informationen über eine einzelne Datei"""
        stats = file_path.stat()
        
        info = {
            'name': file_path.name,
            'size': stats.st_size,
            'modified': datetime.datetime.fromtimestamp(stats.st_mtime).isoformat(),
            'type': file_path.suffix,
            'analysis': {}
        }
        
        # Analyse basierend auf Dateityp
        if file_path.suffix.lower() in ['.geojson', '.shp']:
            info['analysis'] = self.analyze_geodata(file_path)
        elif file_path.suffix.lower() == '.py':
            info['analysis'] = self.analyze_python_file(file_path)
            
        return info
    
    def repair_geojson(self, file_path: Path) -> bool:
        """Versucht, eine beschädigte GeoJSON-Datei zu reparieren"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Entferne ungültige Zeichen am Anfang und Ende
            while content and not content.startswith('{'):
                content = content[1:]
            while content and not content.endswith('}'):
                content = content[:-1]
            
            # Versuche, den bereinigten Inhalt zu parsen
            data = json.loads(content)
            
            # Speichere die reparierte Version
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"Konnte GeoJSON nicht reparieren: {str(e)}")
            return False
    
    def handle_corrupted_file(self, file_path: Path):
        """Verschiebt beschädigte Dateien in einen speziellen Ordner"""
        corrupted_dir = self.base_dir / 'data/corrupted'
        new_path = corrupted_dir / file_path.name
        
        try:
            shutil.move(str(file_path), str(new_path))
            self.logger.warning(f"Beschädigte Datei verschoben: {file_path.name} -> data/corrupted/")
        except Exception as e:
            self.logger.error(f"Fehler beim Verschieben der beschädigten Datei {file_path}: {str(e)}")

    def analyze_geodata(self, file_path: Path) -> Dict:
        """Analysiert Geodaten-Dateien"""
        try:
            # Versuche zuerst, die Datei als GeoJSON zu lesen
            if file_path.suffix.lower() == '.geojson':
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    # Versuche die Datei zu reparieren
                    if self.repair_geojson(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        # Wenn die Reparatur fehlschlägt, verschiebe die Datei
                        self.handle_corrupted_file(file_path)
                        return {
                            'error': 'Beschädigte GeoJSON-Datei',
                            'type': 'corrupted_geojson'
                        }
                
                if 'features' in data:
                    return {
                        'type': 'GeoJSON',
                        'feature_count': len(data['features']),
                        'geometry_types': list(set(f['geometry']['type'] for f in data['features'] if 'geometry' in f)),
                        'properties': list(data['features'][0]['properties'].keys()) if data['features'] else []
                    }
            
            # Falls das nicht klappt, versuche es mit GeoPandas
            gdf = gpd.read_file(file_path)
            return {
                'geometry_types': list(gdf.geometry.type.unique()),
                'attributes': list(gdf.columns),
                'feature_count': len(gdf),
                'crs': str(gdf.crs)
            }
        except Exception as e:
            # Bei anderen Fehlern, verschiebe die Datei auch
            self.handle_corrupted_file(file_path)
            return {
                'error': str(e),
                'type': 'corrupted_geodata'
            }
    
    def analyze_python_file(self, file_path: Path) -> Dict:
        """Analysiert Python-Dateien"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            imports = set()
            functions = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.add(n.name)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module)
                elif isinstance(node, ast.FunctionDef):
                    functions.add(node.name)
                    
            return {
                'imports': list(imports),
                'functions': list(functions)
            }
        except Exception as e:
            self.logger.error(f"Fehler bei der Python-Datei-Analyse von {file_path}: {str(e)}")
            return {}
    
    def generate_report(self, file_info: Dict):
        """Generiert einen detaillierten Bericht"""
        report_path = self.base_dir / 'report.txt'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=== Automatisierungssystem Bericht ===\n\n")
            f.write(f"Erstellt am: {datetime.datetime.now().isoformat()}\n\n")
            
            f.write("Gefundene Dateien:\n")
            for path, info in file_info.items():
                f.write(f"\nDatei: {path}\n")
                f.write(f"Größe: {info['size']} Bytes\n")
                f.write(f"Zuletzt geändert: {info['modified']}\n")
                
                if info['analysis']:
                    f.write("Analyse:\n")
                    for key, value in info['analysis'].items():
                        f.write(f"  {key}: {value}\n")
                        
        self.logger.info(f"Bericht erstellt: {report_path}")
    
    def organize_files(self, file_info: Dict):
        """Sortiert Dateien in die entsprechende Verzeichnisstruktur"""
        for file_path, info in file_info.items():
            path = Path(file_path)
            if not path.exists():
                continue
                
            try:
                target_dir = self.determine_target_directory(path, info)
                if target_dir:
                    new_path = self.base_dir / target_dir / path.name
                    if not new_path.exists():  # Verhindere Überschreiben existierender Dateien
                        shutil.move(str(path), str(new_path))
                        self.logger.info(f"Datei verschoben: {path} -> {new_path}")
            except Exception as e:
                self.logger.error(f"Fehler beim Verschieben von {path}: {str(e)}")
    
    def determine_target_directory(self, file_path: Path, info: Dict) -> str:
        """Bestimmt das Zielverzeichnis für eine Datei"""
        # Ignoriere bestimmte Verzeichnisse und Dateien
        ignore_paths = ['env', 'venv', '__pycache__', '.git', 'backups', 'logs', 'data/corrupted']
        if any(x in str(file_path) for x in ignore_paths):
            return None
            
        if file_path.suffix.lower() in ['.py', '.sh']:
            return 'src'
        elif file_path.suffix.lower() in ['.geojson', '.shp', '.tif']:
            return 'data/raw'
        elif file_path.suffix.lower() in ['.log']:
            return 'logs'
        elif file_path.suffix.lower() in ['.json', '.txt', '.md']:
            return 'data/raw'
        return None
    
    def create_backup(self):
        """Erstellt ein Backup aller wichtigen Dateien"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        backup_file = self.base_dir / 'backups' / f'backup_{timestamp}.zip'
        
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.base_dir.rglob('*'):
                if file_path.is_file() and not any(x in str(file_path) for x in ['backups', '__pycache__', '.git']):
                    zipf.write(file_path, file_path.relative_to(self.base_dir))
                    
        self.logger.info(f"Backup erstellt: {backup_file}")
    
    def run(self):
        """Führt alle Automatisierungsschritte aus"""
        self.logger.info("Starte Automatisierung...")
        
        # Analysiere Dateien
        file_info = self.analyze_files()
        
        # Generiere Bericht
        self.generate_report(file_info)
        
        # Organisiere Dateien
        self.organize_files(file_info)
        
        # Erstelle Backup
        self.create_backup()
        
        self.logger.info("Automatisierung abgeschlossen")

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, organizer: AutoOrganizer):
        self.organizer = organizer
        
    def on_modified(self, event):
        if not event.is_directory:
            self.organizer.run()

def main():
    base_dir = os.getcwd()
    
    # Cloud-Konfiguration (optional)
    cloud_config = None  # Deaktiviere Cloud-Upload für den Test
    
    organizer = AutoOrganizer(base_dir, cloud_config)
    
    # Sofortige Ausführung der Hauptfunktionen
    organizer.run()
    organizer.create_backup()
    
    # Starte Aufgabenplanung in einem separaten Thread
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(organizer.schedule_tasks)
        
        # Überwachung für Änderungen einrichten
        observer = Observer()
        handler = FileChangeHandler(organizer)
        observer.schedule(handler, base_dir, recursive=True)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

if __name__ == "__main__":
    main() 