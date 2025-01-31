// ALKIS Selector Service - Verwaltet die manuelle Auswahl von ALKIS-Definitionen
export class AlkisSelectorService {
    constructor() {
        this.debug = true;
        this.alkisDefinitions = {
            // Basis-Objekte
            'AX_Flurstueck': {
                name: 'Flurstück',
                definition: 'Kleinste Buchungseinheit des Liegenschaftskatasters',
                attributes: [
                    { name: 'flurstuecksnummer', type: 'String', description: 'Eindeutige Nummer des Flurstücks' },
                    { name: 'amtlicheFlaeche', type: 'Real', description: 'Fläche in Quadratmetern' },
                    { name: 'flurnummer', type: 'Integer', description: 'Nummer des Flurs' }
                ]
            },
            'AX_Gebaeude': {
                name: 'Gebäude',
                definition: 'Dauerhaft errichtetes Bauwerk',
                attributes: [
                    { name: 'gebaeudefunktion', type: 'Integer', description: 'Nutzungsart des Gebäudes' },
                    { name: 'baujahr', type: 'Integer', description: 'Jahr der Fertigstellung' },
                    { name: 'dachform', type: 'Integer', description: 'Form des Gebäudedachs' }
                ]
            },
            // Präsentationsobjekte
            'AP_PTO': {
                name: 'Präsentationsobjekt',
                definition: 'Punktförmiges Präsentationsobjekt',
                attributes: [
                    { name: 'art', type: 'String', description: 'Art der Präsentation' },
                    { name: 'darstellungsprioritaet', type: 'Integer', description: 'Priorität bei der Darstellung' }
                ]
            },
            'AP_LTO': {
                name: 'Linien Präsentationsobjekt',
                definition: 'Linienförmiges Präsentationsobjekt',
                attributes: [
                    { name: 'art', type: 'String', description: 'Art der Linienpräsentation' },
                    { name: 'darstellungsprioritaet', type: 'Integer', description: 'Priorität bei der Darstellung' }
                ]
            }
            // Weitere ALKIS-Definitionen hier hinzufügen...
        };
    }

    log(message) {
        if (this.debug) {
            console.log(`[ALKIS-Selector] ${message}`);
        }
    }

    // Zeigt den ALKIS-Auswahldialog
    showSelector(layerName) {
        this.log(`Zeige ALKIS-Auswahl für: ${layerName}`);
        
        // Extrahiere den ALKIS-Typ aus dem Namen
        const alkisType = this.extractAlkisType(layerName);
        
        // Erstelle das Modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'alkisSelectorModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">ALKIS-Definition auswählen</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">ALKIS-Typ auswählen:</label>
                            <select class="form-select" id="alkisTypeSelect">
                                <option value="">Bitte wählen...</option>
                                ${this.buildAlkisOptions(alkisType)}
                            </select>
                        </div>
                        <div id="alkisPreview" class="border rounded p-3 bg-light" style="display: none;">
                            <h6>Vorschau:</h6>
                            <div id="alkisPreviewContent"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>
                        <button type="button" class="btn btn-primary" id="alkisSelectConfirm">Übernehmen</button>
                    </div>
                </div>
            </div>
        `;

        // Füge Modal zum DOM hinzu
        document.body.appendChild(modal);

        // Initialisiere Bootstrap Modal
        const bsModal = new bootstrap.Modal(modal);
        
        // Event-Listener für die Auswahl
        const select = modal.querySelector('#alkisTypeSelect');
        const preview = modal.querySelector('#alkisPreview');
        const previewContent = modal.querySelector('#alkisPreviewContent');
        const confirmBtn = modal.querySelector('#alkisSelectConfirm');
        
        select.addEventListener('change', () => {
            const selectedType = select.value;
            if (selectedType && this.alkisDefinitions[selectedType]) {
                const def = this.alkisDefinitions[selectedType];
                previewContent.innerHTML = this.buildPreviewHtml(def);
                preview.style.display = 'block';
            } else {
                preview.style.display = 'none';
            }
        });
        
        // Zeige Modal
        bsModal.show();
        
        // Rückgabe als Promise
        return new Promise((resolve, reject) => {
            confirmBtn.addEventListener('click', () => {
                const selectedType = select.value;
                if (selectedType && this.alkisDefinitions[selectedType]) {
                    bsModal.hide();
                    resolve(this.alkisDefinitions[selectedType]);
                } else {
                    reject(new Error('Keine ALKIS-Definition ausgewählt'));
                }
            });
            
            modal.addEventListener('hidden.bs.modal', () => {
                modal.remove();
                reject(new Error('Auswahl abgebrochen'));
            });
        });
    }

    // Extrahiert den ALKIS-Typ aus dem Layer-Namen
    extractAlkisType(layerName) {
        const match = layerName.match(/adv_(ax|ap)_(\w+)/i);
        return match ? match[2] : '';
    }

    // Baut die Options für das Select
    buildAlkisOptions(preselect = '') {
        return Object.entries(this.alkisDefinitions)
            .map(([key, def]) => `
                <option value="${key}" ${key === preselect ? 'selected' : ''}>
                    ${def.name} (${key})
                </option>
            `)
            .join('');
    }

    // Baut die Vorschau-HTML
    buildPreviewHtml(definition) {
        return `
            <div class="mb-3">
                <strong>Name:</strong> ${definition.name}
            </div>
            <div class="mb-3">
                <strong>Definition:</strong><br>
                ${definition.definition}
            </div>
            <div>
                <strong>Attribute:</strong>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Typ</th>
                            <th>Beschreibung</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${definition.attributes.map(attr => `
                            <tr>
                                <td>${attr.name}</td>
                                <td><code>${attr.type}</code></td>
                                <td>${attr.description}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // Fügt eine neue ALKIS-Definition hinzu
    addAlkisDefinition(key, definition) {
        if (this.alkisDefinitions[key]) {
            this.log(`ALKIS-Definition ${key} wird überschrieben`);
        }
        this.alkisDefinitions[key] = definition;
    }
}

// Exportiere eine Instanz des ALKIS-Selector-Service
export const alkisSelectorService = new AlkisSelectorService(); 