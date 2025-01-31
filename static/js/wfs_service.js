// WFS Service - Hauptfunktionalität für WFS-Operationen
import { layerInfoService } from './layer_info_service.js';
import { alkisSelectorService } from './alkis_selector_service.js';
import { documentationService } from './documentation_service.js';
import { AiCleanerService } from './ai_cleaner_service.js';

export class WFSService {
    constructor() {
        this.debug = true;
        this.initializeEventListeners();
        this.log('WFS Service initialisiert');
        this.aiCleanerService = new AiCleanerService();
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

            // Zeige den Layer-Container
            const container = document.getElementById('wfs-layers-container');
            if (container) {
                container.style.display = 'block';
            }

            // Aktiviere den AI Cleaner Service
            this.aiCleanerService.addCleanButton();

        } catch (error) {
            this.showError(`Fehler beim Laden der Layer: ${error.message}`);
        }
    }

    async displayLayers(data) {
        const container = document.getElementById('wfs-layers-container');
        const tbody = document.getElementById('layer-list');
        
        if (!container || !tbody) {
            this.showError('Layer-Container nicht gefunden');
            return;
        }
        
        tbody.innerHTML = '';
        container.style.display = 'block';
        
        Object.entries(data.layers).forEach(([namespace, namespaceLayers]) => {
            Object.entries(namespaceLayers).forEach(([layerName, layerInfo]) => {
                const row = tbody.insertRow();
                
                // Checkbox
                const checkCell = row.insertCell();
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'form-check-input layer-checkbox';
                checkCell.appendChild(checkbox);
                
                // Layer Name
                const nameCell = row.insertCell();
                nameCell.textContent = layerInfo.name;
                nameCell.setAttribute('data-title', layerInfo.title || '');
                
                // Titel
                const titleCell = row.insertCell();
                titleCell.textContent = layerInfo.title || '';
                
                // Gesäuberter Name (zunächst leer)
                const cleanedCell = row.insertCell();
                cleanedCell.textContent = '';
                
                // Erklärung (zunächst leer)
                const explanationCell = row.insertCell();
                explanationCell.textContent = '';
                
                // Aktionen
                const actionCell = row.insertCell();
                const infoButton = document.createElement('button');
                infoButton.className = 'btn btn-info btn-sm';
                infoButton.innerHTML = '<i class="bi bi-info-circle"></i>';
                infoButton.onclick = () => this.showLayerInfo(layerInfo);
                actionCell.appendChild(infoButton);
            });
        });
        
        // Event-Listener für "Alle auswählen" Checkbox
        const selectAllCheckbox = document.getElementById('select-all-layers');
        if (selectAllCheckbox) {
            selectAllCheckbox.onchange = (e) => {
                const checkboxes = document.querySelectorAll('.layer-checkbox');
                checkboxes.forEach(cb => cb.checked = e.target.checked);
            };
        }
    }

    showLayerInfo(layerInfo) {
        layerInfoService.showLayerInfo(layerInfo);
    }
}

// Exportiere eine Instanz des WFS-Service
export const wfsService = new WFSService(); 