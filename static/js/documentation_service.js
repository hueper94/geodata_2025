// Documentation Service - Verwaltet den Zugriff auf verschiedene Dokumentationsquellen
import { promptService } from './prompt_service.js';

export class DocumentationService {
    constructor() {
        this.debug = true;
        this.dlmDefinitions = null;
        this.dlmPdfPath = '/docs/OK Basis-DLM 7.1.1.pdf'; // Korrekter Name der PDF
        this.cache = new Map(); // Cache für bereits gesuchte Layer
        this.searchInProgress = new Map(); // Tracking für laufende Suchen
    }

    log(message, data = null) {
        if (this.debug) {
            console.log(`[Documentation] ${message}`, data || '');
        }
    }

    // Lädt die Basis DLM Definitionen aus der PDF
    async loadDLMDefinitions() {
        if (this.dlmDefinitions) {
            return this.dlmDefinitions;
        }

        try {
            const response = await fetch('/api/load-dlm-definitions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    pdfPath: this.dlmPdfPath
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            this.dlmDefinitions = await response.json();
            return this.dlmDefinitions;
        } catch (error) {
            this.log('Fehler beim Laden der DLM-Definitionen:', error);
            throw error;
        }
    }

    // Holt die Layer-Definition mit dem passenden Prompt
    async getLayerDefinition(layerName, type, layerInfo = {}) {
        const cacheKey = `${type}_${layerName}`;
        
        // Debug-Logging
        this.log(`Verarbeite Layer-Definition für: ${layerName}, Typ: ${type}`);
        this.log(`Layer-Info: ${JSON.stringify(layerInfo)}`);
        
        // Prüfe Cache
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        try {
            let result;
            
            // Typ-spezifische Verarbeitung
            switch(type.toLowerCase()) {
                case 'basis_dlm':
                    // Versuche zuerst die Definition aus der PDF zu laden
                    try {
                        const dlmDefinitions = await this.loadDLMDefinitions();
                        const dlmKey = this.fallbackNameCleaning(layerName);
                        this.log(`Suche nach DLM-Definition für: ${dlmKey}`);
                        
                        if (dlmDefinitions && dlmDefinitions[dlmKey]) {
                            this.log(`DLM-Definition gefunden für: ${dlmKey}`);
                            result = {
                                name: dlmDefinitions[dlmKey].name || layerName,
                                definition: dlmDefinitions[dlmKey].definition,
                                attributes: dlmDefinitions[dlmKey].attributes || [],
                                source: 'Basis DLM Dokumentation (PDF)'
                            };
                        } else {
                            this.log(`Keine DLM-Definition gefunden für: ${dlmKey}, verwende KI-Generierung`);
                            // Wenn keine Definition gefunden, verwende KI
                            result = await this._generateEnhancedExplanation(layerName, type, layerInfo);
                        }
                    } catch (error) {
                        this.log(`Fehler beim Laden der DLM-Definition: ${error.message}`);
                        // Bei Fehler verwende KI
                        result = await this._generateEnhancedExplanation(layerName, type, layerInfo);
                    }
                    break;

                case 'alkis':
                case 'standard':
                default:
                    result = await this._generateEnhancedExplanation(layerName, type, layerInfo);
                    break;
            }

            // Speichere im Cache
            this.cache.set(cacheKey, result);
            return result;
        } catch (error) {
            this.log(`Fehler bei der Layer-Definition: ${error.message}`);
            throw error;
        }
    }

    async _generateEnhancedExplanation(layerName, type, layerInfo) {
        // Wähle den richtigen Prompt-Typ basierend auf dem Layer-Typ
        const promptType = type.toLowerCase() === 'basis_dlm' ? 'layer_analysis' : 'explanation_generation';
        
        const prompt = promptService.formatPrompt(type, promptType, {
            layerName,
            layerInfo,
            requestedInfo: {
                definition: true,
                attributes: true,
                examples: true,
                modeling: true
            }
        });

        if (!prompt) {
            throw new Error(`Kein Prompt gefunden für Typ: ${type}`);
        }

        try {
            const response = await fetch('/api/generate-explanation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    system_prompt: prompt.system,
                    user_prompt: prompt.user,
                    layer_name: layerName,
                    source_type: type,
                    layer_info: layerInfo
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            return {
                name: result.name || layerName,
                definition: result.definition || 'Keine Definition verfügbar',
                attributes: result.attributes || [],
                modeling: result.modeling || 'Keine Modellierungsinformationen verfügbar',
                examples: result.examples || [],
                source: this._getSourceName(type, result.source)
            };
        } catch (error) {
            this.log(`Fehler bei der erweiterten Erklärungsgenerierung: ${error.message}`);
            return {
                name: this.fallbackNameCleaning(layerName),
                definition: 'Keine Definition verfügbar',
                attributes: [],
                source: 'Lokale Verarbeitung (Fallback)'
            };
        }
    }

    _getSourceName(type, customSource) {
        if (customSource) return customSource;
        
        switch (type) {
            case 'alkis':
                return 'ALKIS-Dokumentation (KI-unterstützt)';
            case 'basis_dlm':
                return 'Basis DLM Dokumentation (KI-unterstützt)';
            default:
                return 'KI-generierte Beschreibung';
        }
    }

    // Generiert eine Erklärung mit dem passenden Prompt
    async generateExplanation(layerName, sourceType) {
        const prompt = promptService.formatPrompt(
            sourceType || 'standard',
            'explanation_generation',
            { layerName }
        );

        if (!prompt) {
            throw new Error(`Kein Prompt gefunden für Typ: ${sourceType}`);
        }

        const response = await fetch('/api/generate-explanation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                system_prompt: prompt.system,
                user_prompt: prompt.user,
                layer_name: layerName,
                source_type: sourceType
            })
        });

        if (!response.ok) {
            throw new Error(`Server-Fehler: ${response.status}`);
        }

        return await response.json();
    }

    // Bereinigt einen Layer-Namen
    async cleanLayerName(name) {
        try {
            const prompt = promptService.formatPrompt('general', 'name_cleaning', { layerName: name });
            if (!prompt) {
                this.log('Kein Prompt für Namensbereinigung gefunden, verwende Fallback');
                return this.fallbackNameCleaning(name);
            }

            const response = await fetch('/api/clean-name', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    system_prompt: prompt.system,
                    user_prompt: prompt.user,
                    layer_name: name
                })
            });

            if (!response.ok) {
                this.log(`Server-Fehler bei Namensbereinigung: ${response.status}`);
                return this.fallbackNameCleaning(name);
            }

            const data = await response.json();
            
            // Prüfe ob die API-Antwort das erwartete Format hat
            if (!data || !data.cleaned_name) {
                this.log('Unerwartetes API-Antwortformat:', data);
                return this.fallbackNameCleaning(name);
            }

            return data.cleaned_name;
        } catch (error) {
            this.log('Fehler bei der Namensbereinigung:', error);
            return this.fallbackNameCleaning(name);
        }
    }

    // Fallback für die Namensbereinigung
    fallbackNameCleaning(name) {
        this.log(`Verwende Fallback-Bereinigung für: ${name}`);
        
        try {
            // Entferne bekannte Präfixe
            let cleanedName = name.replace(/^(adv_|ax_|ap_|dlm_|basis_)/i, '');
            
            // Ersetze Unterstriche und Bindestriche durch Leerzeichen
            cleanedName = cleanedName.replace(/[_-]/g, ' ');
            
            // Teile an Großbuchstaben
            cleanedName = cleanedName.replace(/([A-Z])/g, ' $1');
            
            // Entferne doppelte Leerzeichen und trimme
            cleanedName = cleanedName.replace(/\s+/g, ' ').trim();
            
            // Erster Buchstabe groß, Rest klein
            cleanedName = cleanedName.charAt(0).toUpperCase() + 
                         cleanedName.slice(1).toLowerCase();
            
            // Jedes Wort mit Großbuchstaben beginnen
            cleanedName = cleanedName.replace(/\b\w/g, c => c.toUpperCase());
            
            this.log(`Bereinigte Version: ${cleanedName}`);
            return cleanedName;
        } catch (error) {
            this.log('Fehler bei der Fallback-Bereinigung:', error);
            return name; // Im Fehlerfall Original zurückgeben
        }
    }

    // Hilfsmethode für zusätzliche Informationen
    getAdditionalInfo(sourceType, data) {
        switch (sourceType) {
            case 'alkis':
                return {
                    practicalUse: data.practicalUse
                };
            case 'basis_dlm':
                return {
                    modeling: data.modeling
                };
            default:
                return {
                    content: data.content,
                    useCases: data.useCases
                };
        }
    }

    // Hilfsmethode für den Quellennamen
    getSourceName(sourceType) {
        switch (sourceType) {
            case 'alkis':
                return 'ALKIS-Dokumentation';
            case 'basis_dlm':
                return 'Basis DLM Dokumentation (PDF)';
            default:
                return 'KI-generierte Beschreibung';
        }
    }

    // Neue Methode zur Verarbeitung bereinigter Layer durch die KI
    async processCleanedLayers(cleanedLayers) {
        this.log('Verarbeite bereinigte Layer:', cleanedLayers);

        try {
            const response = await fetch('/api/process-cleaned-layers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    layers: cleanedLayers
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server-Fehler: ${response.status}`);
            }

            const results = await response.json();
            this.log('KI-Verarbeitung abgeschlossen:', results);

            if (!results.processed_layers || results.processed_layers.length === 0) {
                throw new Error('Keine verarbeiteten Layer in der API-Antwort');
            }

            // Cache-Update für verarbeitete Layer
            results.processed_layers.forEach(layer => {
                const cacheKey = `${layer.original_name}_${layer.type}`;
                this.cache.set(cacheKey, {
                    name: layer.cleaned_name,
                    definition: layer.explanation,
                    timestamp: Date.now()
                });
            });

            return results.processed_layers;

        } catch (error) {
            this.log('Fehler bei der KI-Verarbeitung:', error);
            throw error;
        }
    }
}

// Exportiere eine Instanz des Documentation-Service
export const documentationService = new DocumentationService(); 