import openai
import tiktoken
import json
import logging

logger = logging.getLogger(__name__)

class ChatGPTService:
    def __init__(self, api_key):
        self.api_key = api_key
        openai.api_key = api_key

    def berechne_tokens(self, text, model="gpt-4"):
        """Berechnet die Anzahl der Tokens in einem Text"""
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        return len(tokens)

    def frage_chatgpt(self, prompt, model="gpt-3.5-turbo", max_tokens=500, temperature=0.7):
        """Sendet eine Anfrage an ChatGPT"""
        try:
            # Entferne verbotene Tokens
            forbidden_tokens = ["<|fim_prefix|>", "<|fim_middle|>", "<|fim_suffix|>", "<|endoftext|>"]
            for token in forbidden_tokens:
                prompt = prompt.replace(token, "")

            # Berechne die Token-Menge und begrenze den Text
            token_limit = 4096 - max_tokens
            gesamt_text_tokens = self.berechne_tokens(prompt)
            
            if gesamt_text_tokens > token_limit:
                prompt = prompt[:token_limit]

            response = openai.Completion.create(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response["choices"][0]["text"]
        except Exception as e:
            logger.error(f"Fehler bei der ChatGPT-Anfrage: {str(e)}")
            raise RuntimeError(f"Fehler bei der Anfrage: {e}")

    def clean_layer_names(self, layers, custom_prompt=None):
        """Säubert Layer-Namen mit Hilfe von ChatGPT"""
        try:
            # Standard-Prompt oder benutzerdefinierter Prompt
            prompt = custom_prompt or "Bitte säubere und vereinfache diese GIS-Layer-Namen. Entferne technische Präfixe, mache sie benutzerfreundlich und füge eine kurze Erklärung hinzu."
            
            # Erstelle den Prompt für ChatGPT
            layer_list = "\n".join([f"- {layer['title']}" for layer in layers])
            full_prompt = f"{prompt}\n\nLayer-Namen:\n{layer_list}\n\nBitte gib die gesäuberten Namen im JSON-Format zurück, z.B.:\n{{\n  'layers': [\n    {{'id': 'original_name', 'title': 'Gesäuberter Name', 'explanation': 'Kurze Erklärung'}}\n  ]\n}}"
            
            # Sende Anfrage an ChatGPT
            response = self.frage_chatgpt(full_prompt)
            
            # Extrahiere JSON aus der Antwort
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError("Keine gültige JSON-Antwort von ChatGPT erhalten")
                
        except Exception as e:
            logger.error(f"Fehler beim Säubern der Layer-Namen: {str(e)}")
            raise 