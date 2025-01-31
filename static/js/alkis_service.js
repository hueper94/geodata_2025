// ALKIS Service - Verwaltet ALKIS-spezifische Funktionen
export class AlkisService {
    constructor() {
        this.debug = true;
    }

    log(message) {
        if (this.debug) {
            console.log(`[ALKIS] ${message}`);
        }
    }

    // Prüft ob es sich um einen ALKIS-Layer handelt
    isAlkisLayer(layerName) {
        return layerName.toLowerCase().includes('adv_ax_') || 
               layerName.toLowerCase().includes('adv_ap_');
    }

    // Extrahiert den ALKIS-Objekttyp aus dem Layer-Namen
    getAlkisObjectType(layerName) {
        const match = layerName.match(/adv_(ax|ap)_(\w+)/i);
        return match ? match[2] : null;
    }

    // Holt die ALKIS-Definition vom Server
    async getAlkisDefinition(layerName) {
        this.log(`Hole ALKIS-Definition für: ${layerName}`);
        
        try {
            const response = await fetch('/api/get-layer-info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    layer_name: layerName,
                    is_alkis: true
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }
            
            const data = await response.json();
            return {
                definition: data.explanation,
                attributes: data.attributes || [],
                source: data.source || 'ALKIS-Dokumentation'
            };
            
        } catch (error) {
            this.log('Fehler beim Laden der ALKIS-Definition:', error);
            throw error;
        }
    }

    // Formatiert ALKIS-Attribute für die Anzeige
    formatAlkisAttributes(attributes) {
        return attributes.map(attr => ({
            name: this.formatAttributeName(attr.name),
            type: this.formatAttributeType(attr.type),
            description: attr.description || this.getDefaultDescription(attr.name)
        }));
    }

    // Formatiert einen ALKIS-Attributnamen
    formatAttributeName(name) {
        return name
            .replace(/([A-Z])/g, ' $1') // Fügt Leerzeichen vor Großbuchstaben ein
            .replace(/^./, str => str.toUpperCase()) // Erster Buchstabe groß
            .trim();
    }

    // Formatiert einen ALKIS-Attributtyp
    formatAttributeType(type) {
        const typeMap = {
            'AX_Datentyp': 'ALKIS-Datentyp',
            'Integer': 'Ganzzahl',
            'Real': 'Dezimalzahl',
            'Boolean': 'Ja/Nein',
            'Date': 'Datum',
            'String': 'Text'
        };
        return typeMap[type] || type;
    }

    // Liefert eine Standard-Beschreibung für bekannte ALKIS-Attribute
    getDefaultDescription(name) {
        const descriptionMap = {
            'objektidentifikator': 'Eindeutige ALKIS-Objektkennung',
            'lebenszeitintervall': 'Zeitraum der Gültigkeit des Objekts',
            'modellart': 'Art des ALKIS-Modells',
            'anlass': 'Grund für die Erfassung/Änderung',
            'zustaendigeStelle': 'Zuständige Stelle für das Objekt'
        };
        return descriptionMap[name.toLowerCase()] || '';
    }

    // Erstellt eine benutzerfreundliche Zusammenfassung der ALKIS-Daten
    createAlkisSummary(definition, attributes) {
        return {
            title: 'ALKIS-Objektinformationen',
            definition: definition,
            attributeGroups: this.groupAttributes(attributes),
            technicalInfo: this.extractTechnicalInfo(attributes)
        };
    }

    // Gruppiert ALKIS-Attribute nach Kategorien
    groupAttributes(attributes) {
        const groups = {
            'Basis': [],
            'Fachlich': [],
            'Technisch': [],
            'Sonstige': []
        };
        
        attributes.forEach(attr => {
            if (this.isBaseAttribute(attr.name)) {
                groups['Basis'].push(attr);
            } else if (this.isTechnicalAttribute(attr.name)) {
                groups['Technisch'].push(attr);
            } else if (this.isProfessionalAttribute(attr.name)) {
                groups['Fachlich'].push(attr);
            } else {
                groups['Sonstige'].push(attr);
            }
        });
        
        return groups;
    }

    // Prüft ob es sich um ein Basis-Attribut handelt
    isBaseAttribute(name) {
        const baseAttributes = [
            'objektidentifikator',
            'name',
            'bezeichnung',
            'kennung'
        ];
        return baseAttributes.includes(name.toLowerCase());
    }

    // Prüft ob es sich um ein technisches Attribut handelt
    isTechnicalAttribute(name) {
        const technicalAttributes = [
            'lebenszeitintervall',
            'modellart',
            'anlass',
            'zustaendigestelle'
        ];
        return technicalAttributes.includes(name.toLowerCase());
    }

    // Prüft ob es sich um ein fachliches Attribut handelt
    isProfessionalAttribute(name) {
        return !this.isBaseAttribute(name) && 
               !this.isTechnicalAttribute(name) &&
               !name.toLowerCase().startsWith('_');
    }

    // Extrahiert technische Informationen aus den Attributen
    extractTechnicalInfo(attributes) {
        const technicalInfo = {};
        attributes.forEach(attr => {
            if (this.isTechnicalAttribute(attr.name)) {
                technicalInfo[this.formatAttributeName(attr.name)] = {
                    type: this.formatAttributeType(attr.type),
                    description: attr.description || this.getDefaultDescription(attr.name)
                };
            }
        });
        return technicalInfo;
    }
}

// Exportiere eine Instanz des ALKIS-Service
export const alkisService = new AlkisService(); 