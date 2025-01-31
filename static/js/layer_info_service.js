// Layer Info Service - Verwaltet die Anzeige von Layer-Informationen
import { alkisSelectorService } from './alkis_selector_service.js';

export class LayerInfoService {
    constructor() {
        this.debug = true;
        this.modal = null;
        this.modalTitle = null;
        this.modalBody = null;
        this.initializeModal();
    }

    log(message) {
        if (this.debug) {
            console.log(`[LayerInfo] ${message}`);
        }
    }

    // Initialisiert das Modal
    initializeModal() {
        this.modal = document.getElementById('layer-info-modal');
        if (!this.modal) {
            // Erstelle Modal wenn nicht vorhanden
            this.modal = document.createElement('div');
            this.modal.id = 'layer-info-modal';
            this.modal.className = 'modal fade';
            this.modal.setAttribute('tabindex', '-1');
            this.modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Layer-Informationen</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body"></div>
                    </div>
                </div>
            `;
            document.body.appendChild(this.modal);
        }
        
        this.modalTitle = this.modal.querySelector('.modal-title');
        this.modalBody = this.modal.querySelector('.modal-body');
    }

    // Zeigt die Layer-Informationen im Modal an
    async showLayerInfo(layerName, layerTitle, definition) {
        this.log(`Zeige Informationen für Layer: ${layerName}`);
        
        if (!this.modal || !this.modalTitle || !this.modalBody) {
            this.log('Modal nicht initialisiert');
            return;
        }
        
        try {
            // Bootstrap Modal anzeigen
            const bsModal = new bootstrap.Modal(this.modal);
            
            // Setze Titel und zeige Lade-Animation
            this.modalTitle.textContent = `Layer-Informationen: ${layerTitle || layerName}`;
            this.modalBody.innerHTML = '<div class="spinner-border" role="status"><span class="visually-hidden">Lädt...</span></div>';
            
            // Modal anzeigen
            bsModal.show();
            
            // HTML für Layer-Informationen erstellen
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
                            <td>${layerTitle || layerName}</td>
                        </tr>
                        <tr>
                            <th>Typ:</th>
                            <td>${definition.source}</td>
                        </tr>
                    </table>
                </div>`;
            
            // Layer-Definition
            if (definition.definition) {
                infoHtml += `
                    <div class="mb-4">
                        <h5>Layer-Definition</h5>
                        <div class="alert alert-info">
                            ${definition.definition}
                        </div>
                    </div>`;
            }
            
            // Attribute
            if (definition.attributes && definition.attributes.length > 0) {
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
                                ${definition.attributes.map(attr => `
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
            
            // Zusätzliche Informationen
            if (definition.additionalInfo) {
                infoHtml += `
                    <div class="mb-4">
                        <h5>Zusätzliche Informationen</h5>
                        <div class="alert alert-secondary">
                            ${this.formatAdditionalInfo(definition.additionalInfo)}
                        </div>
                    </div>`;
            }
            
            infoHtml += '</div>';
            
            // Setze den HTML-Inhalt
            this.modalBody.innerHTML = infoHtml;
            
        } catch (error) {
            this.log('Fehler beim Anzeigen der Layer-Informationen:', error);
            this.modalBody.innerHTML = `
                <div class="alert alert-danger">
                    Fehler beim Laden der Layer-Informationen: ${error.message}
                </div>`;
        }
    }

    // Formatiert zusätzliche Informationen
    formatAdditionalInfo(info) {
        if (typeof info === 'string') return info;
        
        let html = '';
        if (info.practicalUse) {
            html += `<p><strong>Praktische Anwendung:</strong><br>${info.practicalUse}</p>`;
        }
        if (info.modeling) {
            html += `<p><strong>Modellierung:</strong><br>${info.modeling}</p>`;
        }
        if (info.content) {
            html += `<p><strong>Inhalt:</strong><br>${info.content}</p>`;
        }
        if (info.useCases && Array.isArray(info.useCases)) {
            html += `
                <p><strong>Anwendungsfälle:</strong></p>
                <ul>
                    ${info.useCases.map(useCase => `<li>${useCase}</li>`).join('')}
                </ul>`;
        }
        return html || 'Keine zusätzlichen Informationen verfügbar';
    }

    // Prüft ob es sich um einen ALKIS-Layer handelt
    isAlkisLayer(layerName) {
        return layerName.toLowerCase().includes('adv_ax_') || 
               layerName.toLowerCase().includes('adv_ap_');
    }

    // Lädt die Standard-Definition für nicht-ALKIS Layer
    async loadStandardDefinition(layerName, container) {
        try {
            const data = await this.fetchLayerInfo(layerName, false);
            container.innerHTML = await this.buildDetailedInfoHtml(data, false);
        } catch (error) {
            this.log('Fehler beim Laden der Layer-Informationen:', error);
            container.innerHTML = this.buildErrorHtml(error);
        }
    }

    // Holt die Layer-Informationen vom Server
    async fetchLayerInfo(layerName, isAlkisLayer) {
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
        
        return await response.json();
    }

    // Baut die detaillierten Informationen HTML
    async buildDetailedInfoHtml(data, isAlkisLayer) {
        let html = `
            <div class="mb-4">
                <h5>${isAlkisLayer ? 'ALKIS-Definition' : 'Beschreibung'}</h5>
                <div class="alert alert-info">
                    ${data.explanation}
                </div>
            </div>`;
        
        // Attribute hinzufügen
        if (data.attributes?.length > 0) {
            html += `
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
        
        // Quelle hinzufügen
        if (data.source) {
            html += `
                <div class="mb-4">
                    <h5>Quelle</h5>
                    <div class="alert alert-secondary">
                        ${data.source}
                    </div>
                </div>`;
        }
        
        return html + '</div>';
    }

    // Baut die Fehler-HTML
    buildErrorHtml(error) {
        return `
            <div class="alert alert-danger">
                Fehler beim Laden der Layer-Informationen: ${error.message}
            </div>`;
    }
}

// Exportiere eine Instanz des Layer Info Service
export const layerInfoService = new LayerInfoService(); 