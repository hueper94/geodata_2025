import json
import os
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class OpenAIHelper:
    def __init__(self, config_path='config/config.json', prompts_dir='prompts'):
        self.prompts_dir = prompts_dir
        self.load_config(config_path)
        try:
            self.client = OpenAI(api_key=self.api_key)
            # Teste die Verbindung
            self.client.models.list()
            logger.info("OpenAI-Verbindung erfolgreich hergestellt")
        except Exception as e:
            logger.error(f"Fehler bei der OpenAI-Initialisierung: {e}")
            raise
        
    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('openai_api_key')
                if not self.api_key:
                    raise ValueError("Kein API-Key in der Konfiguration gefunden")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {e}")
            raise
            
    def load_prompt_config(self, prompt_name):
        try:
            with open(os.path.join(self.prompts_dir, f"{prompt_name}.json"), 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Prompt-Konfiguration: {str(e)}")
            raise

    def clean_layer_names_batch(self, layer_names):
        """Verarbeitet eine Liste von Layer-Namen in einem Batch und fügt Erklärungen hinzu."""
        try:
            if not layer_names:
                raise ValueError("Keine Layer-Namen zum Verarbeiten")
                
            names_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(layer_names)])
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """Du bist ein Experte für GIS-Daten und ALKIS (Amtliches Liegenschaftskatasterinformationssystem).
                    
                    Deine Aufgaben sind:
                    1. Bereinige die Layer-Namen:
                       - Entferne technische Präfixe wie 'adv_AX_' oder 'adv_AP_'
                       - Trenne zusammengeschriebene Wörter mit Leerzeichen
                       - Formatiere sie einheitlich und benutzerfreundlich
                       - Wenn der Name unklar ist, verwende die offizielle Bezeichnung aus der ALKIS-Dokumentation
                       
                    2. Füge eine präzise Erklärung hinzu:
                       - Nutze die offiziellen Erklärungen aus der ALKIS-Dokumentation
                       - Halte die Erklärung kurz und verständlich
                       - Füge wichtige Attribute oder Besonderheiten hinzu
                       
                    Beispiele:
                    - 'adv_AX_Gebaeude' -> 'Gebäude (Amtliche Gebäudedaten mit Attributen wie Gebäudenutzung, Baujahr und Geschosszahl)'
                    - 'adv_AX_Flurstueck' -> 'Flurstück (Amtliche Grundstücksfläche mit Flurstücksnummer und Grundbuchbezug)'
                    
                    Antworte im Format:
                    Name: [bereinigter Name]
                    Erklärung: [offizielle Erklärung aus ALKIS]
                    ---"""},
                    {"role": "user", "content": f"""Bitte bereinige diese Layer-Namen und füge die offiziellen ALKIS-Erklärungen hinzu.
                    Beachte dabei:
                    - Nutze die offiziellen Bezeichnungen und Erklärungen aus der ALKIS-Dokumentation
                    - Behalte wichtige Fachbegriffe bei
                    - Füge relevante Attribute in der Erklärung hinzu
                    
                    Layer-Namen:
                    {names_list}"""}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Verarbeite die Antwort
            response_text = response.choices[0].message.content.strip()
            entries = response_text.split('---\n')
            
            cleaned_names = []
            explanations = []
            
            for entry in entries:
                if not entry.strip():
                    continue
                    
                lines = entry.strip().split('\n')
                name = ''
                explanation = ''
                
                for line in lines:
                    if line.startswith('Name:'):
                        name = line.replace('Name:', '').strip()
                    elif line.startswith('Erklärung:'):
                        explanation = line.replace('Erklärung:', '').strip()
                
                if name:
                    cleaned_names.append(name)
                    explanations.append(explanation)
            
            if not cleaned_names:
                raise ValueError("Keine bereinigten Namen in der API-Antwort")
                
            return {
                'names': cleaned_names,
                'explanations': explanations
            }
            
        except Exception as e:
            logger.error(f"Fehler bei der Batch-Verarbeitung: {str(e)}")
            raise ValueError(f"Fehler bei der KI-Verarbeitung: {str(e)}")
            
    def clean_layer_name(self, layer_name):
        """Einzelne Layer-Namen-Verarbeitung (für Kompatibilität)"""
        try:
            result = self.clean_layer_names_batch([layer_name])
            return {
                'name': result['names'][0] if result['names'] else layer_name,
                'explanation': result['explanations'][0] if result['explanations'] else ''
            }
        except Exception as e:
            logger.error(f"Fehler bei der KI-Verarbeitung: {str(e)}")
            raise 

    def get_alkis_definition(self, layer_name):
        """Holt die ALKIS-Definition für einen Layer-Namen."""
        try:
            # Bereinige den Layer-Namen für die Suche
            search_name = layer_name.lower().replace('adv_ax_', '').replace('adv_ap_', '')
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """Du bist ein ALKIS-Experte. Deine Aufgabe ist es, 
                    die offizielle ALKIS-Definition und Attribute für den angegebenen Layer zu liefern.
                    
                    Antworte im Format:
                    {
                        "definition": "Offizielle ALKIS-Definition",
                        "attributes": [
                            {
                                "name": "Attributname",
                                "type": "Datentyp",
                                "description": "Beschreibung des Attributs"
                            }
                        ]
                    }
                    
                    Verwende NUR offizielle ALKIS-Definitionen und Attribute."""},
                    {"role": "user", "content": f"Gib mir die ALKIS-Definition und Attribute für: {search_name}"}
                ],
                temperature=0.1,
                response_format={ "type": "json_object" }
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der ALKIS-Definition: {str(e)}")
            raise ValueError(f"ALKIS-Definition nicht gefunden: {str(e)}")
            
    def generate_layer_explanation(self, layer_name, attributes=None):
        """Generiert eine Erklärung für einen Layer basierend auf Namen und Attributen."""
        try:
            attributes_text = ""
            if attributes:
                attributes_text = "\nVerfügbare Attribute:\n" + "\n".join([
                    f"- {attr['name']} ({attr['type']})"
                    for attr in attributes
                ])
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """Du bist ein GIS-Experte. Deine Aufgabe ist es, 
                    Layer-Namen zu analysieren und verständliche Erklärungen zu generieren.
                    
                    Berücksichtige dabei:
                    1. Die Bedeutung des Layer-Namens
                    2. Die verfügbaren Attribute
                    3. Mögliche Anwendungsfälle
                    
                    Antworte im Format:
                    {
                        "explanation": "Deine Erklärung",
                        "source": "Quelle der Information (falls bekannt)"
                    }"""},
                    {"role": "user", "content": f"""Erkläre diesen Layer:
                    Name: {layer_name}
                    {attributes_text}"""}
                ],
                temperature=0.3,
                response_format={ "type": "json_object" }
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Fehler bei der Erklärungsgenerierung: {str(e)}")
            return {
                "explanation": f"Keine Erklärung verfügbar: {str(e)}",
                "source": "Fehler bei der KI-Generierung"
            } 