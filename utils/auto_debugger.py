import logging
import time
import json
from functools import wraps
import traceback
import sys
from datetime import datetime

class AutoDebugger:
    def __init__(self, log_file='debug_log.json'):
        self.log_file = log_file
        self.debug_data = []
        self.start_time = None
        
        # Logger Setup
        self.logger = logging.getLogger('AutoDebugger')
        self.logger.setLevel(logging.DEBUG)
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File Handler
        file_handler = logging.FileHandler('debug.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def start_debug_session(self):
        """Startet eine neue Debug-Session"""
        self.start_time = time.time()
        self.debug_data = []
        self.logger.info('Neue Debug-Session gestartet')

    def log_step(self, step_name, data=None, error=None):
        """Loggt einen einzelnen Debug-Schritt"""
        timestamp = datetime.now().isoformat()
        step_data = {
            'timestamp': timestamp,
            'step': step_name,
            'duration': time.time() - self.start_time if self.start_time else 0,
            'data': data,
            'error': str(error) if error else None
        }
        self.debug_data.append(step_data)
        
        # Log basierend auf dem Vorhandensein eines Fehlers
        if error:
            self.logger.error(f'{step_name}: {error}')
        else:
            self.logger.info(f'{step_name}: Erfolgreich')
            if data:
                self.logger.debug(f'Daten: {json.dumps(data, indent=2)}')

    def save_debug_log(self):
        """Speichert den Debug-Log in einer Datei"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.debug_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f'Debug-Log gespeichert in {self.log_file}')
        except Exception as e:
            self.logger.error(f'Fehler beim Speichern des Debug-Logs: {e}')

def auto_debug(func):
    """Decorator für automatisches Debugging von Funktionen"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        debugger = AutoDebugger()
        debugger.start_debug_session()
        
        try:
            # Funktionsaufruf loggen
            debugger.log_step(f'Start {func.__name__}', {
                'args': str(args),
                'kwargs': str(kwargs)
            })
            
            # Funktion ausführen
            result = func(*args, **kwargs)
            
            # Erfolg loggen
            debugger.log_step(f'Ende {func.__name__}', {
                'result': str(result)
            })
            
            return result
            
        except Exception as e:
            # Fehler loggen
            debugger.log_step(f'Fehler in {func.__name__}', error=e)
            debugger.log_step('Traceback', {
                'traceback': traceback.format_exc()
            })
            raise
        finally:
            debugger.save_debug_log()
    
    return wrapper 