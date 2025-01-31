// AI Cleaner Service - Verantwortlich für die KI-basierte Säuberung von Layer-Namen
class AiCleanerService {
    constructor() {
        this.debug = true;
        this.buttonAdded = false;
        this.initializeEventListeners();
        this.log('AI Cleaner Service initialisiert');
    }

    // Debug-Logging
    log(message) {
        if (this.debug) {
            console.log(`[AI] ${message}`);
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
        
        // Warte auf Layer-Laden Event
        document.addEventListener('layersLoaded', () => {
            this.log('Layer wurden geladen, füge Clean-Button hinzu');
            this.addCleanButton();
        });

        // Beobachte Container-Sichtbarkeit
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target.style.display === 'block' && !this.buttonAdded) {
                    this.addCleanButton();
                }
            });
        });

        const container = document.getElementById('wfs-layers-container');
        if (container) {
            observer.observe(container, { 
                attributes: true, 
                attributeFilter: ['style'] 
            });
        }
    }

    // Füge Clean-Button hinzu
    addCleanButton() {
        if (this.buttonAdded) {
            this.log('Button bereits vorhanden');
            return;
        }

        const container = document.getElementById('wfs-layers-container');
        if (!container || container.style.display === 'none') {
            this.log('Container für Clean-Button nicht gefunden oder nicht sichtbar');
            return;
        }

        const toolsContainer = container.querySelector('.tools-container');
        if (!toolsContainer) {
            this.log('FEHLER: Tools-Container nicht gefunden');
            return;
        }

        const cleanButton = document.createElement('button');
        cleanButton.type = 'button';
        cleanButton.className = 'btn btn-success';
        cleanButton.innerHTML = '<i class="bi bi-magic"></i> Layer-Namen mit KI säubern';
        cleanButton.addEventListener('click', () => this.cleanSelectedLayers());
        
        toolsContainer.appendChild(cleanButton);
        this.buttonAdded = true;
        this.log('Clean-Button erfolgreich hinzugefügt');
    }

    // Hole ausgewählte Layer
    getSelectedLayers() {
        const checkboxes = document.querySelectorAll('#layer-list input[type="checkbox"]:checked');
        const layers = [];
        
        checkboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const nameCell = row.querySelector('td:nth-child(2)');
                const titleCell = row.querySelector('td:nth-child(3)');
                if (nameCell && titleCell) {
                    layers.push({
                        name: nameCell.textContent,
                        title: titleCell.textContent
                    });
                }
            }
        });
        
        return layers;
    }

    // Säubere ausgewählte Layer
    async cleanSelectedLayers() {
        const layers = this.getSelectedLayers();
        if (layers.length === 0) {
            this.showError('Bitte wählen Sie mindestens einen Layer aus');
            return;
        }

        try {
            const response = await fetch('/api/clean-layer-names', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    layers: layers,
                    prompt: "Bitte säubere und vereinfache diese GIS-Layer-Namen. Entferne technische Präfixe, " +
                           "mache sie benutzerfreundlich und füge eine kurze Erklärung hinzu. " +
                           "Format: Kurzer, klarer Name + (optional) Erklärung in Klammern."
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(
                    errorData?.error || 
                    `Server-Fehler: ${response.status} - ${response.statusText}`
                );
            }

            const data = await response.json();
            this.log('Server-Antwort erhalten:', data);

            if (data.error) {
                throw new Error(data.error);
            }

            this.updateLayerNames(data.cleaned_layers);
            this.showSuccess('Layer-Namen wurden erfolgreich gesäubert');
            
        } catch (error) {
            this.log('Fehler bei der Säuberung:', error);
            this.showError(`Fehler bei der Säuberung der Layer-Namen: ${error.message}`);
        }
    }

    // Aktualisiere Layer-Namen in der Tabelle
    updateLayerNames(cleanedLayers) {
        const cleanedMap = new Map(cleanedLayers.map(layer => [layer.id, layer]));
        
        document.querySelectorAll('#layer-list tr').forEach(row => {
            const nameCell = row.querySelector('td:nth-child(2)');
            const titleCell = row.querySelector('td:nth-child(3)');
            const cleanedNameCell = row.querySelector('td:nth-child(4)') || document.createElement('td');
            const explanationCell = row.querySelector('td:nth-child(5)') || document.createElement('td');
            
            if (nameCell) {
                const originalName = nameCell.textContent;
                const cleanedLayer = cleanedMap.get(originalName);
                
                if (cleanedLayer) {
                    // Füge die Zellen hinzu, falls sie noch nicht existieren
                    if (!row.contains(cleanedNameCell)) {
                        row.insertBefore(cleanedNameCell, row.querySelector('td:last-child'));
                    }
                    if (!row.contains(explanationCell)) {
                        row.insertBefore(explanationCell, row.querySelector('td:last-child'));
                    }
                    
                    // Aktualisiere die Inhalte
                    cleanedNameCell.textContent = cleanedLayer.cleaned_name || '';
                    cleanedNameCell.title = cleanedLayer.cleaned_name || '';
                    
                    explanationCell.textContent = cleanedLayer.explanation || '';
                    explanationCell.title = cleanedLayer.explanation || '';
                    
                    // Füge Styling hinzu
                    cleanedNameCell.classList.add('text-success');
                    explanationCell.classList.add('text-muted', 'small');
                    
                    this.log(`Layer aktualisiert: ${originalName} -> ${cleanedLayer.cleaned_name}`);
                }
            }
        });
    }
}

// Exportiere die Klasse
export { AiCleanerService }; 