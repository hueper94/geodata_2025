// WFS Service - Hauptfunktionalität für WFS-Operationen
import { layerInfoService } from './layer_info_service.js';
import { alkisSelectorService } from './alkis_selector_service.js';
import { documentationService } from './documentation_service.js';

export class WFSService {
    constructor() {
        this.debug = true;
        this.initializeEventListeners();
        this.log('WFS Service initialisiert');
    }

    // Debug-Logging
    log(message) {
        if (this.debug) {
            console.log(`[WFS] ${message}`);
        }
    }

    // Zeige Fehlermeldung
    showError(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => errorDiv.style.display = 'none', 5000);
        }
        this.log(`Fehler: ${message}`);
    }

    // Zeige Erfolgsmeldung
    showSuccess(message) {
        const successDiv = document.getElementById('success-message');
        if (successDiv) {
            successDiv.textContent = message;
            successDiv.style.display = 'block';
            setTimeout(() => successDiv.style.display = 'none', 3000);
        }
        this.log(`Erfolg: ${message}`);
    }

    // Initialisiere Event-Listener
    initializeEventListeners() {
        this.log('Initialisiere Event-Listener');
        
        // Formular Submit
        const form = document.getElementById('wfs_form');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                this.log('Formular wurde abgeschickt');
                await this.loadLayers();
            });
        } else {
            this.showError('WFS Formular nicht gefunden');
        }
    }

    // Lade Layer vom WFS-Server
    async loadLayers() {
        const urlInput = document.getElementById('wfs_url');
        if (!urlInput || !urlInput.value.trim()) {
            this.showError('Bitte geben Sie eine WFS-URL ein');
            return;
        }

        const url = urlInput.value.trim();
        this.log(`Lade Layer von: ${url}`);

        try {
            const formData = new FormData();
            formData.append('wfs_url', url);

            const response = await fetch('/get_layers', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server-Fehler: ${response.status}`);
            }

            const data = await response.json();
            this.log(`Server-Antwort erhalten: ${Object.keys(data.layers || {}).length} Layer`);

            if (data.status === 'error') {
                throw new Error(data.message || 'Unbekannter Fehler');
            }

            await this.displayLayers(data);
            this.showSuccess('Layer erfolgreich geladen');

        } catch (error) {
            this.showError(`Fehler beim Laden der Layer: ${error.message}`);
        }
    }

    // Zeige Layer in der Tabelle an
    async displayLayers(data) {
        const container = document.getElementById('wfs-layers-container');
        const tbody = document.getElementById('layer-list');
        
        if (!container || !tbody) {
            this.showError('Layer-Container nicht gefunden');
            return;
        }
        
        // Leere die Tabelle
        tbody.innerHTML = '';
        
        // Zeige den Container
        container.style.display = 'block';
        
        // Header-Zeile anpassen
        const thead = container.querySelector('thead tr');
        if (thead) {
            thead.innerHTML = `
                <th>
                    <div class="d-flex align-items-center">
                        <input type="checkbox" id="select-all-layers" class="form-check-input me-2">
                        <select id="global-data-type" class="form-select form-select-sm" style="width: auto;">
                            <option value="">Datentyp wählen...</option>
                            <option value="standard">Standard WFS</option>
                            <option value="alkis">ALKIS Daten</option>
                            <option value="basis_dlm">Basis DLM</option>
                        </select>
                    </div>
                </th>
                <th>Original Name <i class="bi bi-info-circle text-info" title="Klicken Sie auf das Info-Symbol für Details"></i></th>
                <th>Gesäuberter Name</th>
            `;

            // Event-Listener für "Alle auswählen" Checkbox
            const selectAllCheckbox = thead.querySelector('#select-all-layers');
            if (selectAllCheckbox) {
                selectAllCheckbox.addEventListener('change', async (e) => {
                    const checkboxes = tbody.querySelectorAll('.layer-checkbox');
                    const isChecked = e.target.checked;
                    
                    // Alle Checkboxen setzen
                    checkboxes.forEach(cb => cb.checked = isChecked);
                    
                    // Wenn ausgewählt und globaler Datentyp gesetzt ist, wende ihn auf alle an
                    const globalType = thead.querySelector('#global-data-type').value;
                    if (isChecked && globalType) {
                        const selectedRows = tbody.querySelectorAll('tr');
                        for (const row of selectedRows) {
                            await this.updateLayerType(row, globalType);
                        }
                    }
                    
                    this.log(`Alle Layer ${isChecked ? 'ausgewählt' : 'abgewählt'}`);
                });
            }

            // Event-Listener für globale Datentyp-Auswahl
            const globalTypeSelect = thead.querySelector('#global-data-type');
            if (globalTypeSelect) {
                globalTypeSelect.addEventListener('change', async (e) => {
                    const selectedType = e.target.value;
                    if (!selectedType) return;

                    // Hole alle ausgewählten Zeilen
                    const checkedRows = Array.from(tbody.querySelectorAll('tr:has(.layer-checkbox:checked)'));
                    if (checkedRows.length === 0) {
                        this.showError('Bitte wählen Sie mindestens einen Layer aus');
                        return;
                    }

                    // Debug: Zeige ausgewählte Zeilen
                    this.log(`Ausgewählte Zeilen: ${checkedRows.length}`);
                    
                    // Sammle Layer-Informationen mit Validierung und Debug-Logging
                    const layerList = [];
                    checkedRows.forEach((row, index) => {
                        const nameElement = row.querySelector('.original-name');
                        if (!nameElement) {
                            this.log(`Fehler: Kein Name-Element in Zeile ${index + 1}`);
                            return;
                        }
                        
                        const originalName = nameElement.textContent.trim();
                        if (!originalName) {
                            this.log(`Fehler: Leerer Name in Zeile ${index + 1}`);
                            return;
                        }

                        this.log(`Verarbeite Layer ${index + 1}: ${originalName}`);
                        
                        const layerInfo = {
                            name: originalName,
                            title: nameElement.title || originalName,
                            description: row.dataset.description || '',
                            namespace: row.dataset.namespace || '',
                            attributes: row.dataset.attributes ? JSON.parse(row.dataset.attributes) : []
                        };
                        
                        this.log(`Layer-Info gesammelt:`, layerInfo);
                        layerList.push(layerInfo);
                    });

                    this.log(`Gesammelte Layer-Informationen (${layerList.length}):`, layerList);

                    if (layerList.length === 0) {
                        this.showError('Keine gültigen Layer-Namen gefunden');
                        return;
                    }

                    // Zeige Lade-Animation
                    const progressDiv = document.createElement('div');
                    progressDiv.className = 'alert alert-info';
                    progressDiv.innerHTML = `
                        <div class="d-flex align-items-center">
                            <div class="spinner-border spinner-border-sm me-2" role="status">
                                <span class="visually-hidden">Lädt...</span>
                            </div>
                            <span>Verarbeite ${layerList.length} Layer...</span>
                        </div>
                    `;
                    document.getElementById('message-container').appendChild(progressDiv);

                    try {
                        // Debug: Zeige API-Anfrage
                        const requestData = {
                            layers: layerList,
                            type: selectedType
                        };
                        this.log('Sende API-Anfrage:', requestData);

                        // Sende die Layer-Informationen zur Verarbeitung
                        const response = await fetch('/api/clean-layer-names', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(requestData)
                        });

                        // Debug: Zeige API-Antwort Status
                        this.log('API-Antwort Status:', response.status);

                        if (!response.ok) {
                            const errorData = await response.json();
                            this.log('API-Fehlermeldung:', errorData);
                            throw new Error(errorData.error || `Server-Fehler: ${response.status}`);
                        }

                        const results = await response.json();
                        this.log('API-Antwort erhalten:', results);

                        if (!results.cleaned_layers || results.cleaned_layers.length === 0) {
                            throw new Error('Keine bereinigten Namen in der API-Antwort');
                        }

                        // Sammle bereinigte Layer für KI-Verarbeitung
                        const cleanedLayersForAI = results.cleaned_layers.map(cleanedLayer => ({
                            original_name: cleanedLayer.original_name,
                            cleaned_name: cleanedLayer.cleaned_name,
                            type: selectedType,
                            namespace: layerList.find(l => l.name === cleanedLayer.original_name)?.namespace || '',
                            attributes: layerList.find(l => l.name === cleanedLayer.original_name)?.attributes || []
                        }));

                        this.log('Sende bereinigte Layer an KI:', cleanedLayersForAI);

                        // Sende bereinigte Namen an Documentation Service für KI-Verarbeitung
                        try {
                            const aiResults = await documentationService.processCleanedLayers(cleanedLayersForAI);
                            this.log('KI-Verarbeitung abgeschlossen:', aiResults);

                            // Aktualisiere die Zeilen mit den KI-Ergebnissen
                            aiResults.forEach(aiResult => {
                                const row = checkedRows.find(row => 
                                    row.querySelector('.original-name').textContent.trim() === aiResult.original_name
                                );
                                
                                if (row) {
                                    const cleanedNameCell = row.querySelector('.cleaned-name');
                                    if (cleanedNameCell) {
                                        cleanedNameCell.textContent = aiResult.cleaned_name;
                                        this.log(`Name aktualisiert: ${aiResult.original_name} -> ${aiResult.cleaned_name}`);
                                    }
                                    
                                    row.dataset.layerType = selectedType;
                                    row.dataset.layerDefinition = JSON.stringify({
                                        name: aiResult.cleaned_name,
                                        definition: aiResult.explanation || ''
                                    });
                                }
                            });

                        } catch (aiError) {
                            this.log('Fehler bei der KI-Verarbeitung:', aiError);
                            // Fallback auf lokale Bereinigung
                            results.cleaned_layers.forEach(cleanedLayer => {
                                const row = checkedRows.find(row => 
                                    row.querySelector('.original-name').textContent.trim() === cleanedLayer.original_name
                                );
                                
                                if (row) {
                                    const cleanedNameCell = row.querySelector('.cleaned-name');
                                    if (cleanedNameCell) {
                                        cleanedNameCell.textContent = cleanedLayer.cleaned_name;
                                        this.log(`Name aktualisiert (Fallback): ${cleanedLayer.original_name} -> ${cleanedLayer.cleaned_name}`);
                                    }
                                }
                            });
                        }

                        // Entferne Lade-Animation und zeige Erfolg
                        progressDiv.remove();
                        this.showSuccess(`${results.cleaned_layers.length} Layer wurden erfolgreich verarbeitet`);

                    } catch (error) {
                        progressDiv.remove();
                        this.showError('Fehler bei der Layer-Verarbeitung: ' + error.message);
                        this.log('Fehler bei der Verarbeitung:', error);
                    }
                });
            }
        }
        
        // Sammle alle Layer für die Batch-Verarbeitung
        const allLayers = [];
        
        Object.entries(data.layers).forEach(([namespace, layers]) => {
            Object.entries(layers).forEach(([name, layer]) => {
                // Erweiterte Layer-Informationen
                const layerInfo = {
                    id: `${namespace}_${name}`,
                    name: layer.name,
                    title: layer.title || layer.name,
                    namespace: namespace,
                    attributes: layer.attributes || [],
                    description: layer.abstract || layer.description || ''
                };
                allLayers.push(layerInfo);
            });
        });
        
        // Erstelle die Tabellenzeilen
        const rows = allLayers.map(layer => {
            const row = document.createElement('tr');
            row.dataset.layerId = layer.id;
            row.dataset.layerType = 'standard'; // Standard-Typ als Default
            row.dataset.namespace = layer.namespace;
            row.dataset.attributes = JSON.stringify(layer.attributes);
            row.dataset.description = layer.description;
            
            // Checkbox
            const checkboxCell = document.createElement('td');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input layer-checkbox';
            checkbox.dataset.name = layer.name;
            checkboxCell.appendChild(checkbox);
            
            // Original Name mit Info-Button
            const nameCell = document.createElement('td');
            const nameContainer = document.createElement('div');
            nameContainer.className = 'd-flex align-items-center justify-content-between';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = layer.name;
            nameSpan.title = layer.name;
            nameSpan.className = 'original-name';
            nameContainer.appendChild(nameSpan);
            
            const infoButton = document.createElement('button');
            infoButton.className = 'btn btn-sm btn-link p-0 ms-2';
            infoButton.innerHTML = '<i class="bi bi-info-circle text-info"></i>';
            infoButton.title = 'Detaillierte Layer-Informationen anzeigen';
            infoButton.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                try {
                    const layerType = row.dataset.layerType || 'standard';
                    const definition = await documentationService.getLayerDefinition(layer.name, layerType);
                    layerInfoService.showLayerInfo(layer.name, layer.title, definition);
                } catch (error) {
                    this.showError(`Fehler beim Laden der Layer-Informationen: ${error.message}`);
                }
            });
            nameContainer.appendChild(infoButton);
            
            nameCell.appendChild(nameContainer);
            
            // Gesäuberter Name (initial leer)
            const cleanedNameCell = document.createElement('td');
            cleanedNameCell.classList.add('cleaned-name');
            cleanedNameCell.textContent = ''; // Initial leer
            
            // Füge Zellen zur Reihe hinzu
            row.appendChild(checkboxCell);
            row.appendChild(nameCell);
            row.appendChild(cleanedNameCell);
            
            return row;
        });
        
        // Füge alle Zeilen zur Tabelle hinzu
        rows.forEach(row => tbody.appendChild(row));

        this.log('Layer-Tabelle aktualisiert');
        
        // Löse layersLoaded Event aus
        const event = new CustomEvent('layersLoaded', {
            detail: {
                ...data,
                allLayers
            },
            bubbles: true
        });
        document.dispatchEvent(event);
        this.log('LayersLoaded Event ausgelöst');
    }

    // Hilfsmethode zum Aktualisieren des Layer-Typs
    async updateLayerType(row, selectedType, layerInfo) {
        try {
            // Stelle sicher, dass layerInfo vollständig ist
            if (!layerInfo || !layerInfo.name) {
                const originalName = row.querySelector('.original-name').textContent;
                const title = row.querySelector('.original-name').title;
                layerInfo = {
                    name: originalName,
                    title: title,
                    description: row.dataset.description || ''
                };
            }

            // Debug-Logging
            this.log(`Verarbeite Layer: ${JSON.stringify(layerInfo)}`);
            
            // Speichere den Typ in der Zeile
            row.dataset.layerType = selectedType;
            
            try {
                // Versuche die Definition vom Documentation Service zu holen
                const definition = await documentationService.getLayerDefinition(
                    layerInfo.name,
                    selectedType,
                    {
                        title: layerInfo.title,
                        description: layerInfo.description,
                        originalName: layerInfo.name,
                        namespace: row.dataset.namespace || '',
                        attributes: row.dataset.attributes ? JSON.parse(row.dataset.attributes) : []
                    }
                );

                if (definition) {
                    row.dataset.layerDefinition = JSON.stringify(definition);
                    
                    // Aktualisiere den bereinigten Namen
                    const cleanedNameCell = row.querySelector('.cleaned-name');
                    if (cleanedNameCell) {
                        cleanedNameCell.textContent = definition.name || this.cleanLayerName(layerInfo.name, selectedType);
                    }
                } else {
                    throw new Error('Keine Definition vom Documentation Service erhalten');
                }
            } catch (error) {
                this.log('Fehler beim Laden der Definition:', error);
                // Fallback: Lokale Namensbereinigung
                const cleanedName = this.cleanLayerName(layerInfo.name, selectedType);
                const cleanedNameCell = row.querySelector('.cleaned-name');
                if (cleanedNameCell) {
                    cleanedNameCell.textContent = cleanedName;
                }
            }
        } catch (error) {
            this.showError(`Fehler bei der Aktualisierung von "${layerInfo?.name || 'unbekannt'}": ${error.message}`);
            throw error;
        }
    }

    // Verbesserte Namensbereinigung mit Typ-spezifischer Logik
    cleanLayerName(name, type = 'standard') {
        try {
            switch (type.toLowerCase()) {
                case 'alkis':
                    return this.cleanAlkisName(name);
                case 'basis_dlm':
                    return this.cleanBasisDLMName(name);
                default:
                    return this.cleanStandardName(name);
            }
        } catch (error) {
            this.log('Fehler bei der Namensbereinigung:', error);
            return name; // Gib im Fehlerfall den Original-Namen zurück
        }
    }

    // Spezifische Bereinigung für ALKIS-Namen
    cleanAlkisName(name) {
        return name
            .replace(/^(adv_|ax_|ap_)/i, '')
            .split(/(?=[A-Z])|[_\s]+/)
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    // Spezifische Bereinigung für Basis-DLM-Namen
    cleanBasisDLMName(name) {
        return name
            .replace(/^(dlm_|basis_)/i, '')
            .split(/[_\s]+/)
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    // Standard-Namensbereinigung
    cleanStandardName(name) {
        return name
            .split(/(?=[A-Z])|[_\s]+/)
            .map(word => word.trim())
            .filter(word => word.length > 0)
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    // Zeige Layer-Informationen im Modal
    async showLayerInfo(layerName, layerTitle) {
        this.log(`Zeige Informationen für Layer: ${layerName}`);
        
        const modal = document.getElementById('attributeModal');
        const modalTitle = modal.querySelector('.modal-title');
        const modalBody = modal.querySelector('.modal-body');
        
        if (!modal || !modalTitle || !modalBody) {
            this.showError('Modal nicht gefunden');
            return;
        }
        
        modalTitle.textContent = 'Layer-Informationen';
        modalBody.innerHTML = '<div class="spinner-border" role="status"><span class="visually-hidden">Lädt...</span></div>';
        
        // Bootstrap Modal anzeigen
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        try {
            // Prüfe ob es ein ALKIS-Layer ist
            const isAlkisLayer = layerName.toLowerCase().includes('adv_ax_') || 
                               layerName.toLowerCase().includes('adv_ap_');
            
            let infoHtml = '<div class="layer-info-container">';
            
            // Basis-Informationen
            infoHtml += `
                <div class="mb-4">
                    <h5>Basis-Informationen</h5>
                    <table class="table table-sm">
                        <tr>
                            <th>Layer-Name:</th>
                            <td>${layerName}</td>
                        </tr>
                        <tr>
                            <th>Titel:</th>
                            <td>${layerTitle}</td>
                        </tr>
                        <tr>
                            <th>Typ:</th>
                            <td>${isAlkisLayer ? 'ALKIS-Layer' : 'Standard WFS-Layer'}</td>
                        </tr>
                    </table>
                </div>`;
            
            // Hole ALKIS-Definition oder generiere KI-Erklärung
            try {
                const response = await fetch('/api/get-layer-info', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        layer_name: layerName,
                        is_alkis: isAlkisLayer
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`Server-Fehler: ${response.status}`);
                }
                
                const data = await response.json();
                
                // Füge ALKIS-Definition oder KI-Erklärung hinzu
                infoHtml += `
                    <div class="mb-4">
                        <h5>${isAlkisLayer ? 'ALKIS-Definition' : 'Beschreibung'}</h5>
                        <div class="alert alert-info">
                            ${data.explanation}
                        </div>
                    </div>`;
                
                // Füge Attribute hinzu, wenn vorhanden
                if (data.attributes && data.attributes.length > 0) {
                    infoHtml += `
                        <div class="mb-4">
                            <h5>Verfügbare Attribute</h5>
                            <table class="table table-sm table-hover">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Beschreibung</th>
                                        <th>Typ</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${data.attributes.map(attr => `
                                        <tr>
                                            <td>${attr.name}</td>
                                            <td>${attr.description || '-'}</td>
                                            <td><code>${attr.type || '-'}</code></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>`;
                }
                
                // Füge Quelle hinzu, wenn vorhanden
                if (data.source) {
                    infoHtml += `
                        <div class="mb-4">
                            <h5>Quelle</h5>
                            <div class="alert alert-secondary">
                                ${data.source}
                            </div>
                        </div>`;
                }
                
            } catch (error) {
                this.log('Fehler beim Laden der Layer-Informationen:', error);
                infoHtml += `
                    <div class="alert alert-warning">
                        Fehler beim Laden der detaillierten Informationen: ${error.message}
                    </div>`;
            }
            
            infoHtml += '</div>';
            modalBody.innerHTML = infoHtml;
            
        } catch (error) {
            this.log('Fehler beim Anzeigen der Layer-Informationen:', error);
            modalBody.innerHTML = `
                <div class="alert alert-danger">
                    Fehler beim Laden der Layer-Informationen: ${error.message}
                </div>`;
        }
    }

    // Prüft ob es sich um einen ALKIS-Layer handelt
    isAlkisLayer(layerName) {
        return layerName.toLowerCase().includes('adv_ax_') || 
               layerName.toLowerCase().includes('adv_ap_');
    }

    // Neue Methode für Basis DLM Informationen
    async getBasisDLMInfo(layerName) {
        // Hier würden die Informationen aus der PDF kommen
        // Beispiel für die Struktur:
        return {
            name: this.cleanBasisDLMName(layerName),
            definition: "Definition aus der Basis DLM Dokumentation",
            attributes: [
                {
                    name: "Attribut 1",
                    type: "String",
                    description: "Beschreibung aus der DLM-PDF"
                }
                // Weitere Attribute...
            ]
        };
    }
}

// Exportiere eine Instanz des WFS-Service
export const wfsService = new WFSService(); 