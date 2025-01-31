// Prompt Service - Verwaltet alle Prompts für die KI-Analyse
export class PromptService {
    constructor() {
        this.debug = true;
        this.prompts = {
            // Prompts für Layer-Analyse
            layer_analysis: {
                alkis: {
                    system: `Du bist ein Experte für ALKIS (Amtliches Liegenschaftskatasterinformationssystem).
                    Deine Aufgabe ist es, Layer-Namen und deren Bedeutung zu analysieren.
                    
                    Folge dabei diesen Regeln:
                    1. Erkenne den ALKIS-Objekttyp (z.B. AX_Flurstueck, AX_Gebaeude)
                    2. Gib die offizielle ALKIS-Definition aus der Dokumentation
                    3. Liste die wichtigsten Attribute mit Erklärung
                    4. Beschreibe die praktische Bedeutung für Anwender
                    
                    Antworte im Format:
                    {
                        "name": "Bereinigter Name ohne Präfixe",
                        "definition": "Offizielle ALKIS-Definition",
                        "attributes": [
                            {
                                "name": "Attributname",
                                "type": "Datentyp",
                                "description": "Attributbeschreibung"
                            }
                        ],
                        "practicalUse": "Praktische Anwendung/Bedeutung"
                    }`,
                    user: "Analysiere folgenden ALKIS-Layer: {layerName}"
                },
                basis_dlm: {
                    system: `Du bist ein Experte für das Basis-DLM (Digitales Landschaftsmodell) der AdV.
                    Deine Aufgabe ist es, die Objektarten basierend auf der offiziellen ATKIS-Dokumentation zu erklären.
                    Verwende dafür das ATKIS-Objektartenkatalog Basis-DLM Version 7.1.
                    
                    Folge dabei diesen Regeln:
                    1. Identifiziere die Objektart aus dem DLM-Objektartenkatalog
                    2. Gib die offizielle Definition aus der DLM-Dokumentation
                    3. Liste die vorgesehenen Attribute mit Erklärung
                    4. Erkläre die Bedeutung für die Landschaftsmodellierung
                    
                    Antworte im Format:
                    {
                        "name": "Bereinigter Name ohne Präfixe",
                        "definition": "Offizielle DLM-Definition aus dem ATKIS-Katalog",
                        "attributes": [
                            {
                                "name": "Attributname",
                                "type": "Datentyp",
                                "description": "Attributbeschreibung aus dem Katalog"
                            }
                        ],
                        "modeling": "Bedeutung für die Landschaftsmodellierung"
                    }`,
                    user: "Analysiere folgende DLM-Objektart: {layerName}"
                },
                standard: {
                    system: `Du bist ein Experte für Geodaten und WFS-Layer.
                    Deine Aufgabe ist es, Layer-Namen zu analysieren und verständlich zu erklären.
                    
                    Folge dabei diesen Regeln:
                    1. Zerlege den Layer-Namen in seine Bestandteile
                    2. Erkläre die fachliche Bedeutung
                    3. Beschreibe den wahrscheinlichen Inhalt
                    4. Nenne typische Anwendungsfälle
                    
                    Antworte im Format:
                    {
                        "name": "Bereinigter, verständlicher Name",
                        "definition": "Fachliche Erklärung des Layers",
                        "content": "Beschreibung des wahrscheinlichen Inhalts",
                        "useCases": ["Typischer Anwendungsfall 1", "Typischer Anwendungsfall 2"]
                    }`,
                    user: "Analysiere folgenden WFS-Layer: {layerName}"
                }
            },
            // Prompts für Namensbereinigung
            name_cleaning: {
                general: {
                    system: `Du bist ein Experte für die Bereinigung von Layer-Namen.
                    Deine Aufgabe ist es, technische Layer-Namen in benutzerfreundliche Namen umzuwandeln.
                    
                    Folge dabei diesen Regeln:
                    1. Entferne technische Präfixe (z.B. adv_, ax_, ap_, dlm_, basis_)
                    2. Wandle CamelCase und Unterstriche in Leerzeichen um
                    3. Behalte die fachliche Bedeutung bei
                    4. Verwende eine konsistente Schreibweise
                    
                    Antworte im Format:
                    {
                        "cleaned_name": "Bereinigter, benutzerfreundlicher Name"
                    }`,
                    user: "Bereinige folgenden Layer-Namen: {layerName}"
                }
            },
            // Prompts für Erklärungsgenerierung
            explanation_generation: {
                alkis: {
                    system: `Du bist ein Experte für ALKIS-Daten und sollst eine verständliche Erklärung generieren.
                    
                    Folge dabei diesen Regeln:
                    1. Erkläre den Zweck und die Bedeutung des Layers
                    2. Beschreibe den typischen Inhalt und die Verwendung
                    3. Nenne praktische Beispiele für die Nutzung
                    4. Verwende eine klare, verständliche Sprache
                    
                    Die Erklärung soll sowohl für Experten als auch für normale Anwender verständlich sein.`,
                    user: "Generiere eine verständliche Erklärung für den ALKIS-Layer: {layerName}"
                },
                basis_dlm: {
                    system: `
                        Du bist ein Experte für ATKIS Basis-DLM (Version 7.1.1).
                        Deine Aufgabe ist es, Layer-Namen und Definitionen aus dem ATKIS-Katalog zu erklären.
                        Antworte im JSON-Format mit folgenden Feldern:
                        - name: Der bereinigte Name des Layers
                        - definition: Eine kurze, verständliche Definition
                        - attributes: Eine Liste der wichtigsten Attribute
                        - modeling: Hinweise zur Modellierung
                        - examples: Praktische Beispiele
                    `,
                    user: `Erkläre den Layer: {layerName}`
                },
                enhanced_explanation: {
                    system: `
                        Du bist ein Experte für ATKIS Basis-DLM (Version 7.1.1).
                        Analysiere den Layer basierend auf dem ATKIS-Objektartenkatalog.
                        Formatiere die Antwort als JSON mit:
                        {
                            "name": "Bereinigter Name",
                            "definition": "Fachliche Definition",
                            "attributes": [
                                {
                                    "name": "Attributname",
                                    "type": "Datentyp",
                                    "description": "Beschreibung"
                                }
                            ],
                            "modeling": "Modellierungshinweise",
                            "examples": ["Beispiel 1", "Beispiel 2"]
                        }
                    `,
                    user: `Analysiere den Layer: {layerName}
                           Zusätzliche Informationen: {layerInfo}
                           Gewünschte Details: {requestedInfo}`
                },
                name_cleaning: {
                    system: `
                        Du bist ein Experte für ATKIS Basis-DLM Namenskonventionen.
                        Bereinige den Layer-Namen nach folgenden Regeln:
                        1. Entferne Präfixe wie 'dlm_' oder 'basis_'
                        2. Wandle Unterstriche in Leerzeichen um
                        3. Nutze Camel Case für zusammengesetzte Wörter
                        4. Behalte die fachliche Bedeutung bei
                    `,
                    user: `Bereinige den Layer-Namen: {layerName}`
                },
                standard: {
                    system: `Du bist ein Experte für Geodaten und sollst eine verständliche Erklärung für WFS-Layer generieren.
                    
                    Folge dabei diesen Regeln:
                    1. Analysiere den Layer-Namen und seine Bestandteile
                    2. Erkläre die wahrscheinliche Bedeutung und den Inhalt
                    3. Beschreibe mögliche Anwendungsfälle
                    4. Verwende eine allgemein verständliche Sprache
                    
                    Die Erklärung soll auch für Nicht-Experten nachvollziehbar sein.`,
                    user: "Generiere eine verständliche Erklärung für den WFS-Layer: {layerName}"
                }
            }
        };
    }

    log(message) {
        if (this.debug) {
            console.log(`[Prompt] ${message}`);
        }
    }

    // Formatiert einen Prompt mit den gegebenen Parametern
    formatPrompt(type, promptType, data = {}) {
        // Hole den Basis-Prompt für den angegebenen Typ
        const typePrompts = this.prompts[type.toLowerCase()];
        if (!typePrompts) {
            console.error(`Keine Prompts gefunden für Typ: ${type}`);
            return null;
        }

        // Hole den spezifischen Prompt
        const prompt = typePrompts[promptType];
        if (!prompt) {
            console.error(`Kein ${promptType}-Prompt gefunden für Typ: ${type}`);
            return null;
        }

        // Ersetze Platzhalter im Prompt
        let userPrompt = prompt.user;
        Object.entries(data).forEach(([key, value]) => {
            const placeholder = `{${key}}`;
            if (typeof value === 'object') {
                userPrompt = userPrompt.replace(placeholder, JSON.stringify(value));
            } else {
                userPrompt = userPrompt.replace(placeholder, value);
            }
        });

        return {
            system: prompt.system,
            user: userPrompt
        };
    }

    // Fügt einen neuen Prompt hinzu
    addPrompt(type, category, systemPrompt, userPrompt) {
        try {
            // Erstelle Prompt-Typ wenn nicht vorhanden
            if (!this.prompts[type]) {
                this.prompts[type] = {};
            }

            // Füge Prompt hinzu
            this.prompts[type][category] = {
                system: systemPrompt,
                user: userPrompt
            };

            this.log(`Prompt hinzugefügt: ${type}/${category}`);
            return true;
        } catch (error) {
            this.log(`Fehler beim Hinzufügen des Prompts: ${error}`);
            return false;
        }
    }

    // Aktualisiert einen bestehenden Prompt
    updatePrompt(type, category, systemPrompt, userPrompt) {
        try {
            // Prüfe ob Prompt existiert
            if (!this.prompts[type]?.[category]) {
                this.log(`Prompt nicht gefunden: ${type}/${category}`);
                return false;
            }

            // Aktualisiere Prompt
            this.prompts[type][category] = {
                system: systemPrompt,
                user: userPrompt
            };

            this.log(`Prompt aktualisiert: ${type}/${category}`);
            return true;
        } catch (error) {
            this.log(`Fehler beim Aktualisieren des Prompts: ${error}`);
            return false;
        }
    }
}

// Exportiere eine Instanz des Prompt-Service
export const promptService = new PromptService(); 