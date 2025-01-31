// Lexikon Service - Verwaltet die Speicherung und Organisation von Layer-Informationen
export class LexiconService {
    constructor() {
        this.debug = true;
        this.cache = new Map();
    }

    log(message, data = null) {
        if (this.debug) {
            console.log(`[Lexicon] ${message}`, data || '');
        }
    }

    // Fügt einen Layer zum Lexikon hinzu
    async addLayer(layerInfo) {
        try {
            const response = await fetch('/api/lexicon/add-layer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    layer: {
                        name: layerInfo.name,
                        title: layerInfo.title,
                        source: {
                            type: layerInfo.sourceType, // 'WMS' oder 'WFS'
                            url: layerInfo.sourceUrl,
                            state: layerInfo.state // Bundesland
                        },
                        cleaned_name: layerInfo.cleanedName,
                        explanation: layerInfo.explanation,
                        attributes: layerInfo.attributes || [],
                        namespace: layerInfo.namespace,
                        description: layerInfo.description
                    }
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            this.log('Layer hinzugefügt:', result);
            return result;
        } catch (error) {
            this.log('Fehler beim Hinzufügen des Layers:', error);
            throw error;
        }
    }

    // Fügt einen Service (WMS/WFS) zum Lexikon hinzu
    async addService(serviceInfo) {
        try {
            const response = await fetch('/api/lexicon/add-service', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    service: {
                        type: serviceInfo.type,
                        url: serviceInfo.url,
                        state: serviceInfo.state,
                        layers: serviceInfo.layers
                    }
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            this.log('Service hinzugefügt:', result);
            return result;
        } catch (error) {
            this.log('Fehler beim Hinzufügen des Services:', error);
            throw error;
        }
    }

    // Prüft ob ein Layer bereits existiert
    async layerExists(name, sourceUrl) {
        try {
            const response = await fetch('/api/lexicon/check-layer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name,
                    source_url: sourceUrl
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            return result.exists;
        } catch (error) {
            this.log('Fehler bei der Layer-Prüfung:', error);
            throw error;
        }
    }

    // Erkennt das Bundesland anhand der URL oder der Layer-Informationen
    detectState(url, layerInfo) {
        const statePatterns = {
            'bayern': /(bayern|by|geoportal\.bayern)/i,
            'brandenburg': /(brandenburg|bb|geoportal\.brandenburg)/i,
            'berlin': /(berlin|be|geoportal\.berlin)/i,
            // Weitere Bundesländer...
        };

        // Prüfe URL
        for (const [state, pattern] of Object.entries(statePatterns)) {
            if (pattern.test(url)) {
                return state;
            }
        }

        // Prüfe Layer-Informationen
        if (layerInfo) {
            const searchText = `${layerInfo.name} ${layerInfo.title} ${layerInfo.description}`.toLowerCase();
            for (const [state, pattern] of Object.entries(statePatterns)) {
                if (pattern.test(searchText)) {
                    return state;
                }
            }
        }

        return 'unknown';
    }

    // Holt alle Layer aus dem Lexikon
    async getLayers(filter = {}) {
        try {
            const response = await fetch('/api/lexicon/get-layers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ filter })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            return result.layers;
        } catch (error) {
            this.log('Fehler beim Abrufen der Layer:', error);
            throw error;
        }
    }

    // Aktualisiert einen bestehenden Layer
    async updateLayer(layerId, updates) {
        try {
            const response = await fetch('/api/lexicon/update-layer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    layer_id: layerId,
                    updates
                })
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const result = await response.json();
            this.log('Layer aktualisiert:', result);
            return result;
        } catch (error) {
            this.log('Fehler beim Aktualisieren des Layers:', error);
            throw error;
        }
    }
}

// Exportiere eine Instanz des Lexikon-Service
export const lexiconService = new LexiconService(); 