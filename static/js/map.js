// Globale Variablen
let map;
let currentLayer;
let currentWMSLayer;
let layerControl;

// Karte initialisieren
function initMap() {
    map = L.map('map').setView([51.5, 10.5], 6);
    
    // OpenStreetMap als Basiskarte
    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Layer Control initialisieren
    const baseMaps = {
        "OpenStreetMap": osm
    };
    const overlayMaps = {};
    layerControl = L.control.layers(baseMaps, overlayMaps).addTo(map);
}

// WFS-Layer zur Karte hinzufügen
function addGeoJSONToMap(geojsonData, layerName) {
    if (currentLayer) {
        map.removeLayer(currentLayer);
    }

    currentLayer = L.geoJSON(geojsonData, {
        style: function(feature) {
            return {
                color: '#3388ff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.5
            };
        },
        onEachFeature: function(feature, layer) {
            if (feature.properties) {
                const popupContent = createPopupContent(feature.properties);
                layer.bindPopup(popupContent);
                
                // Hover-Effekte
                layer.on({
                    mouseover: function(e) {
                        layer.setStyle({
                            weight: 4,
                            fillOpacity: 0.7
                        });
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                            layer.bringToFront();
                        }
                    },
                    mouseout: function(e) {
                        currentLayer.resetStyle(e.target);
                    },
                    click: function(e) {
                        map.fitBounds(e.target.getBounds());
                    }
                });
            }
        }
    }).addTo(map);

    // Zoom auf Layer-Grenzen
    const bounds = currentLayer.getBounds();
    if (bounds.isValid()) {
        map.fitBounds(bounds);
    }
}

// WMS-Layer zur Karte hinzufügen
function addWMSToMap(url, layers, options = {}) {
    // Wenn ein bestehender WMS-Layer existiert, diesen entfernen
    if (currentWMSLayer) {
        map.removeLayer(currentWMSLayer);
        layerControl.removeLayer(currentWMSLayer);
    }

    // Standard-Optionen mit benutzerdefinierten Optionen zusammenführen
    const wmsOptions = {
        format: 'image/png',
        transparent: true,
        version: '1.3.0',
        attribution: options.attribution || "WMS Layer",
        ...options
    };
    
    // Neuen WMS-Layer erstellen
    currentWMSLayer = L.tileLayer.wms(url, {
        layers: layers,
        ...wmsOptions
    });

    // Layer zur Karte hinzufügen
    currentWMSLayer.addTo(map);
    
    // Layer zum Layer-Control hinzufügen
    layerControl.addOverlay(currentWMSLayer, layers);

    // Wenn eine BoundingBox verfügbar ist, darauf zoomen
    if (options.bbox) {
        const bounds = L.latLngBounds(
            [options.bbox[1], options.bbox[0]],  // südwest
            [options.bbox[3], options.bbox[2]]   // nordost
        );
        map.fitBounds(bounds);
    }
}

// Popup-Inhalt erstellen
function createPopupContent(properties) {
    let content = '<div class="feature-popup">';
    
    // Zeige den Display-Namen als Überschrift
    if (properties.display_name) {
        content += `<h4>${properties.display_name}</h4>`;
    }
    
    // Wichtige Eigenschaften zuerst anzeigen
    const priorityFields = ['Art', 'Nutzung', 'Funktion', 'Typ', 'Status', 'Name', 'Bezeichnung'];
    for (const field of priorityFields) {
        if (properties[field]) {
            content += `<strong>${field}:</strong> ${properties[field]}<br>`;
        }
    }
    
    // Restliche Eigenschaften anzeigen
    content += '<div class="additional-properties">';
    for (const [key, value] of Object.entries(properties)) {
        if (!priorityFields.includes(key) && key !== 'display_name' && value) {
            content += `<strong>${key}:</strong> ${value}<br>`;
        }
    }
    content += '</div></div>';
    
    return content;
}

// Layer-Steuerung
function toggleLayer(layerId, visible) {
    if (visible) {
        if (currentLayer && currentLayer.layerId === layerId) {
            map.addLayer(currentLayer);
        }
        if (currentWMSLayer && currentWMSLayer.layerId === layerId) {
            map.addLayer(currentWMSLayer);
        }
    } else {
        if (currentLayer && currentLayer.layerId === layerId) {
            map.removeLayer(currentLayer);
        }
        if (currentWMSLayer && currentWMSLayer.layerId === layerId) {
            map.removeLayer(currentWMSLayer);
        }
    }
}

// Beispiel-WMS hinzufügen
function addExampleWMS() {
    // NRW Schutzgebiete WMS
    addWMSToMap(
        'https://www.wms.nrw.de/umwelt/schutzgeb',
        'Naturschutzgebiete',
        {
            attribution: '© Land NRW',
            bbox: [5.9, 50.3, 9.5, 52.5]  // Ungefähre BBox für NRW
        }
    );
}

// Download-Funktion
async function downloadLayer(layerId, format = 'geojson') {
    try {
        showLoading('Download wird vorbereitet...');
        const response = await fetch(`/api/download/${layerId}?format=${format}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${layerId}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        hideLoading();
        showNotification('success', 'Download erfolgreich abgeschlossen!');
    } catch (error) {
        console.error('Download error:', error);
        hideLoading();
        showNotification('error', 'Fehler beim Download: ' + error.message);
    }
}

// Attributtabelle anzeigen
function showAttributeTable(layerId) {
    if (!currentLayer) {
        showNotification('warning', 'Kein Layer ausgewählt!');
        return;
    }

    const features = [];
    currentLayer.eachLayer(layer => {
        if (layer.feature && layer.feature.properties) {
            features.push(layer.feature.properties);
        }
    });

    if (features.length === 0) {
        showNotification('warning', 'Keine Attribute verfügbar!');
        return;
    }

    // Modal für Attributtabelle erstellen
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'attributeModal';
    modal.setAttribute('tabindex', '-1');
    
    const modalContent = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Attributtabelle</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr>
                                    ${Object.keys(features[0]).map(key => `<th>${key}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${features.map(feature => `
                                    <tr>
                                        ${Object.values(feature).map(value => `<td>${value || ''}</td>`).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    modal.innerHTML = modalContent;
    document.body.appendChild(modal);
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    modal.addEventListener('hidden.bs.modal', function () {
        document.body.removeChild(modal);
    });
}

// Attributtabelle bearbeiten
function editAttributeTable(layerId) {
    if (!currentLayer) {
        showNotification('warning', 'Kein Layer ausgewählt!');
        return;
    }

    const features = [];
    currentLayer.eachLayer(layer => {
        if (layer.feature && layer.feature.properties) {
            features.push(layer.feature.properties);
        }
    });

    if (features.length === 0) {
        showNotification('warning', 'Keine Attribute verfügbar!');
        return;
    }

    // Modal für Attributtabelle-Bearbeitung erstellen
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'editAttributeModal';
    modal.setAttribute('tabindex', '-1');
    
    const modalContent = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Attributtabelle bearbeiten</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr>
                                    ${Object.keys(features[0]).map(key => `<th>${key}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${features.map((feature, featureIndex) => `
                                    <tr>
                                        ${Object.entries(feature).map(([key, value]) => `
                                            <td>
                                                <input type="text" 
                                                    class="form-control attribute-input" 
                                                    data-feature-index="${featureIndex}"
                                                    data-attribute-key="${key}"
                                                    value="${value || ''}"
                                                >
                                            </td>
                                        `).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>
                    <button type="button" class="btn btn-primary save-attributes-btn">Speichern</button>
                </div>
            </div>
        </div>
    `;
    
    modal.innerHTML = modalContent;
    document.body.appendChild(modal);
    
    const bootstrapModal = new bootstrap.Modal(modal);
    
    // Speichern-Button Event-Handler
    modal.querySelector('.save-attributes-btn').addEventListener('click', async () => {
        const updatedFeatures = [];
        const inputs = modal.querySelectorAll('.attribute-input');
        
        inputs.forEach(input => {
            const featureIndex = parseInt(input.dataset.featureIndex);
            const attributeKey = input.dataset.attributeKey;
            const value = input.value;
            
            if (!updatedFeatures[featureIndex]) {
                updatedFeatures[featureIndex] = {};
            }
            updatedFeatures[featureIndex][attributeKey] = value;
        });
        
        try {
            const response = await fetch(`/api/update-attributes/${layerId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ features: updatedFeatures })
            });
            
            if (!response.ok) {
                throw new Error('Fehler beim Speichern der Attribute');
            }
            
            showNotification('success', 'Attribute erfolgreich gespeichert');
            bootstrapModal.hide();
            
            // Layer neu laden
            loadLayer(layerId);
            
        } catch (error) {
            showNotification('error', error.message);
        }
    });
    
    bootstrapModal.show();
    
    modal.addEventListener('hidden.bs.modal', function () {
        document.body.removeChild(modal);
    });
}

// Hilfsfunktionen für Benachrichtigungen und Ladeanimation
function showNotification(type, message) {
    const notification = document.getElementById('notification');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

function showLoading(message) {
    const loading = document.querySelector('.loading-overlay');
    const loadingText = loading.querySelector('.loading-text');
    loadingText.textContent = message;
    loading.style.display = 'flex';
}

function hideLoading() {
    const loading = document.querySelector('.loading-overlay');
    loading.style.display = 'none';
}

// Event-Listener für die Buttons
document.addEventListener('DOMContentLoaded', function() {
    // Download-Button
    document.querySelectorAll('.download-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const layerId = this.dataset.layerId;
            downloadLayer(layerId);
        });
    });
    
    // Attributtabelle anzeigen
    document.querySelectorAll('.view-attributes-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const layerId = this.dataset.layerId;
            showAttributeTable(layerId);
        });
    });
    
    // Attributtabelle bearbeiten
    document.querySelectorAll('.edit-attributes-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const layerId = this.dataset.layerId;
            editAttributeTable(layerId);
        });
    });
    
    // ATKIS Checkbox für alle Layer
    const atkisAllCheckbox = document.querySelector('.atkis-all-checkbox');
    if (atkisAllCheckbox) {
        atkisAllCheckbox.addEventListener('change', async function() {
            if (this.checked) {
                showLoading('ATKIS-Namen werden für alle Layer synchronisiert...');
                try {
                    const response = await fetch('/api/sync-atkis-all', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        }
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const result = await response.json();
                    hideLoading();
                    showNotification('success', 'ATKIS-Namen wurden für alle Layer synchronisiert!');
                    
                    // Alle Layer neu laden
                    if (result.reloadRequired) {
                        loadAllLayers();
                    }
                } catch (error) {
                    console.error('ATKIS sync error:', error);
                    hideLoading();
                    showNotification('error', 'Fehler bei der ATKIS-Synchronisierung: ' + error.message);
                }
            }
        });
    }
});

// Karte initialisieren wenn das Dokument geladen ist
document.addEventListener('DOMContentLoaded', function() {
    initMap();
}); 