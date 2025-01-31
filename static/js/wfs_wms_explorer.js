// Globale Variablen für aktuelle Layer und Service-Informationen
let currentLayers = null;
let currentServiceUrl = null;
let currentServiceType = null;

// Funktion zum Anzeigen von Nachrichten
function showMessage(type, message) {
    const messageDiv = document.getElementById('message');
    const errorDiv = document.getElementById('error-message');
    const successDiv = document.getElementById('success-message');
    
    // Verstecke alle Nachrichten
    [messageDiv, errorDiv, successDiv].forEach(div => {
        if (div) div.style.display = 'none';
    });
    
    // Zeige die entsprechende Nachricht
    if (type === 'error' && errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    } else if (type === 'success' && successDiv) {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    } else if (messageDiv) {
        messageDiv.className = `alert alert-${type}`;
        messageDiv.textContent = message;
        messageDiv.style.display = 'block';
    }
    
    // Nachricht nach 5 Sekunden ausblenden
    setTimeout(() => {
        [messageDiv, errorDiv, successDiv].forEach(div => {
            if (div) div.style.display = 'none';
        });
    }, 5000);
}

// Funktion zum Anzeigen der Layer in der Tabelle
function displayLayers(layers) {
    const tableBody = document.getElementById('layer-list');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    for (const namespace in layers) {
        for (const layerName in layers[namespace]) {
            const layer = layers[namespace][layerName];
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>
                    <input type="checkbox" class="form-check-input layer-checkbox" 
                           data-name="${layer.name}" data-namespace="${namespace}">
                </td>
                <td>${layer.name}</td>
                <td>${layer.title}</td>
                <td>${layer.name}</td>
                <td>${layer.description || ''}</td>
                <td>
                    <div class="button-container">
                        <button class="btn btn-sm btn-primary view-attributes-btn" 
                                data-name="${layer.name}">
                            <i class="bi bi-eye"></i> Attribute
                        </button>
                    </div>
                </td>
            `;
            
            tableBody.appendChild(row);
        }
    }

    // Zeige den Container an
    const container = document.getElementById('wfs-layers-container');
    if (container) {
        container.style.display = 'block';
    }
}

// Funktion zum Importieren der Layer ins Lexikon
async function importToLexicon(layers, serviceUrl, serviceType) {
    try {
        // Debug-Logging
        console.log('Import-Daten:', {
            layers: layers,
            serviceUrl: serviceUrl,
            serviceType: serviceType
        });

        // Zeige Lade-Overlay
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            const loadingStatus = document.getElementById('loadingStatus');
            if (loadingStatus) {
                loadingStatus.textContent = 'Importiere Layer ins Lexikon...';
            }
            loadingOverlay.style.display = 'flex';
        }
        
        // Bereite Request-Daten vor
        const requestData = {
            layers: layers,
            service_url: serviceUrl,
            service_type: serviceType
        };
        
        console.log('Sende Request an Backend:', requestData);
        console.log('Request-Daten als String:', JSON.stringify(requestData));
        
        const response = await fetch('/import_to_lexicon', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        console.log('Server-Antwort Status:', response.status);
        const result = await response.json();
        console.log('Server-Antwort:', result);
        
        if (result.status === 'success') {
            showMessage('success', result.message);
        } else {
            showMessage('error', result.message || 'Fehler beim Import');
        }
        
    } catch (error) {
        console.error('Detaillierter Fehler beim Import:', error);
        showMessage('error', `Fehler beim Import ins Lexikon: ${error.message}`);
    } finally {
        // Verstecke Lade-Overlay
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }
}

// Button zum Importieren ins Lexikon hinzufügen
function addImportButton() {
    const buttonContainer = document.querySelector('#layer-controls');
    if (!buttonContainer) return;
    
    // Entferne vorhandenen Import-Button falls vorhanden
    const existingButton = buttonContainer.querySelector('.import-button');
    if (existingButton) {
        existingButton.remove();
    }
    
    const importButton = document.createElement('button');
    importButton.textContent = 'In Lexikon importieren';
    importButton.className = 'btn btn-primary import-button mt-2';
    importButton.onclick = function() {
        console.log('Import-Button geklickt');
        console.log('Aktuelle Layer:', currentLayers);
        console.log('Service URL:', currentServiceUrl);
        console.log('Service Type:', currentServiceType);
        
        if (currentLayers && currentServiceUrl) {
            importToLexicon(currentLayers, currentServiceUrl, currentServiceType);
        } else {
            console.error('Keine Layer-Daten verfügbar:', {
                layers: currentLayers,
                url: currentServiceUrl,
                type: currentServiceType
            });
            showMessage('error', 'Keine Layer zum Importieren verfügbar');
        }
    };
    
    buttonContainer.appendChild(importButton);
}

// Event-Listener für das WFS-Formular
document.addEventListener('DOMContentLoaded', function() {
    const wfsForm = document.getElementById('wfs_form');
    if (wfsForm) {
        wfsForm.onsubmit = async function(e) {
            e.preventDefault();
            const wfsUrl = document.getElementById('wfs_url').value;
            if (wfsUrl) {
                try {
                    // Zeige Lade-Overlay
                    const loadingOverlay = document.getElementById('loadingOverlay');
                    if (loadingOverlay) {
                        loadingOverlay.style.display = 'flex';
                    }
                    
                    const formData = new FormData();
                    formData.append('wfs_url', wfsUrl);
                    
                    const response = await fetch('/get_layers', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    console.log('Layer-Laden Ergebnis:', result);
                    
                    if (result.status === 'success') {
                        // Speichere Layer-Informationen
                        currentLayers = result.layers;
                        currentServiceUrl = result.service_url;
                        currentServiceType = result.service_type;
                        
                        console.log('Layer gespeichert:', {
                            layers: currentLayers,
                            url: currentServiceUrl,
                            type: currentServiceType
                        });
                        
                        // Zeige Layer an
                        displayLayers(result.layers);
                        
                        // Füge Import-Button hinzu
                        addImportButton();
                        
                        showMessage('success', result.message);
                    } else {
                        showMessage('error', result.message);
                    }
                    
                } catch (error) {
                    console.error('Detaillierter Fehler beim Laden:', error);
                    showMessage('error', `Fehler beim Laden der Layer: ${error.message}`);
                } finally {
                    // Verstecke Lade-Overlay
                    const loadingOverlay = document.getElementById('loadingOverlay');
                    if (loadingOverlay) {
                        loadingOverlay.style.display = 'none';
                    }
                }
            }
        };
    }

    // Event-Listener für "Alle auswählen" Checkbox
    const selectAllCheckbox = document.getElementById('select-all-layers');
    if (selectAllCheckbox) {
        selectAllCheckbox.onchange = function() {
            const checkboxes = document.querySelectorAll('.layer-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = selectAllCheckbox.checked;
            });
        };
    }
}); 