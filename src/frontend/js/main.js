async function showAttributeTable(wfsUrl, layerName, featureId = null) {
    try {
        const formData = new FormData();
        formData.append('wfs_url', wfsUrl);
        formData.append('layer_name', layerName);
        if (featureId) {
            formData.append('feature_id', featureId);
        }

        const response = await fetch('/get_attributes', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            showError('Fehler beim Laden der Attributtabelle: ' + data.message);
            return;
        }

        // Container für beide Tabellen
        const modalContent = document.createElement('div');
        modalContent.className = 'attribute-tables-container';
        
        // Header mit Titel und Aktionen
        const header = document.createElement('div');
        header.className = 'tables-header';
        
        const title = document.createElement('h2');
        title.textContent = 'Attributtabelle: ' + layerName;
        header.appendChild(title);
        
        // Aktions-Container
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'table-actions';
        
        // Sync-Button nur für ATKIS-Layer
        if (layerName.startsWith('ax_')) {
            const syncButton = document.createElement('button');
            syncButton.className = 'sync-names-btn';
            syncButton.textContent = 'Namen synchronisieren';
            syncButton.onclick = async () => {
                try {
                    syncButton.disabled = true;
                    syncButton.textContent = 'Synchronisiere...';
                    
                    const isAtkis = document.getElementById('global-atkis').checked;
                    
                    const response = await fetch('/sync_atkis_names', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            layer_name: layerName,
                            is_atkis: isAtkis
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        showMessage('Namen erfolgreich synchronisiert');
                    } else {
                        throw new Error(result.message);
                    }
                    
                } catch (error) {
                    console.error('Synchronisierungsfehler:', error);
                    showError('Fehler bei der Synchronisierung: ' + error.message);
                } finally {
                    syncButton.disabled = false;
                    syncButton.textContent = 'Namen synchronisieren';
                }
            };
            actionsContainer.appendChild(syncButton);
        }
        
        header.appendChild(actionsContainer);
        modalContent.appendChild(header);
        
        // Original Tabelle
        const originalTable = createAttributeTable(
            'Original Attributtabelle',
            data.attributes,
            false,
            data.is_atkis
        );
        modalContent.appendChild(originalTable);
        
        // Übersetzte Tabelle (nur für ATKIS nach Synchronisierung)
        if (data.is_atkis && Object.values(data.attributes)[0]?.explanation) {
            const translatedTable = createAttributeTable(
                'Übersetzte Attributtabelle',
                data.attributes,
                true,
                data.is_atkis
            );
            modalContent.appendChild(translatedTable);
        }
        
        // Modal anzeigen
        showModal('Attributtabelle', modalContent);
        
    } catch (error) {
        console.error('Fehler beim Laden der Attributtabelle:', error);
        showError('Fehler beim Laden der Attributtabelle: ' + error.message);
    }
}

function createAttributeTable(title, attributes, translated = false, isAtkis = false) {
    const container = document.createElement('div');
    container.className = 'table-container';
    
    // Tabellen-Header mit Titel und Spaltenauswahl
    const headerContainer = document.createElement('div');
    headerContainer.className = 'table-header';
    
    const tableTitle = document.createElement('h3');
    tableTitle.textContent = title;
    headerContainer.appendChild(tableTitle);
    
    // Spaltenauswahl für diese spezifische Tabelle
    const columnToggle = document.createElement('div');
    columnToggle.className = 'column-toggle';
    columnToggle.innerHTML = '<button class="toggle-columns-btn">Spalten verwalten</button>';
    headerContainer.appendChild(columnToggle);
    
    container.appendChild(headerContainer);
    
    // Spaltenauswahl-Dropdown
    const columnDropdown = document.createElement('div');
    columnDropdown.className = 'column-dropdown';
    columnDropdown.style.display = 'none';
    
    // Checkboxen für Spalten
    Object.keys(attributes).forEach(attrName => {
        const label = document.createElement('label');
        label.className = 'column-checkbox';
        label.innerHTML = `
            <input type="checkbox" checked data-table="${title}" data-column="${attrName}">
            <span>${attrName}</span>
        `;
        columnDropdown.appendChild(label);
    });
    
    container.appendChild(columnDropdown);
    
    // Event-Listener für Spaltenauswahl-Button
    columnToggle.querySelector('.toggle-columns-btn').addEventListener('click', () => {
        const isVisible = columnDropdown.style.display === 'block';
        columnDropdown.style.display = isVisible ? 'none' : 'block';
    });
    
    const table = document.createElement('table');
    table.className = 'attribute-table';
    
    // Tabellenkopf
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    // Spalten erstellen
    Object.keys(attributes).forEach(attrName => {
        const th = document.createElement('th');
        th.textContent = attrName;
        th.dataset.column = attrName;
        th.dataset.table = title;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Tabelleninhalt
    const tbody = document.createElement('tbody');
    const row = document.createElement('tr');
    
    Object.entries(attributes).forEach(([attrName, attrValue]) => {
        const cell = document.createElement('td');
        cell.dataset.column = attrName;
        cell.dataset.table = title;
        
        if (isAtkis && typeof attrValue === 'object') {
            cell.textContent = translated ? attrValue.explanation : attrValue.original;
        } else {
            cell.textContent = Array.isArray(attrValue) ? attrValue.join(', ') : attrValue;
        }
        
        row.appendChild(cell);
    });
    
    tbody.appendChild(row);
    table.appendChild(tbody);
    container.appendChild(table);
    
    // Event-Listener für Checkboxen
    columnDropdown.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            const columnName = e.target.dataset.column;
            const tableName = e.target.dataset.table;
            toggleColumn(columnName, isChecked, tableName);
        });
    });
    
    return container;
}

function toggleColumn(columnName, show, tableName) {
    const elements = document.querySelectorAll(`[data-column="${columnName}"][data-table="${tableName}"]`);
    elements.forEach(element => {
        if (show) {
            element.classList.remove('hidden-column');
        } else {
            element.classList.add('hidden-column');
        }
    });
}

// Event-Listener für Attributtabellen-Button
document.addEventListener('DOMContentLoaded', () => {
    const attributeButtons = document.querySelectorAll('.show-attributes-btn');
    attributeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const wfsUrl = e.target.dataset.wfsUrl;
            const layerName = e.target.dataset.layerName;
            showAttributeTable(wfsUrl, layerName);
        });
    });
});

// Hilfsfunktion zum Anzeigen von Nachrichten
function showMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message success';
    messageDiv.textContent = message;
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}

// Hilfsfunktion zum Anzeigen von Fehlern
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error';
    errorDiv.textContent = message;
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Zusätzliches Styling für Nachrichten
const messageStyle = document.createElement('style');
messageStyle.textContent = `
    .message {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 4px;
        color: white;
        font-weight: 500;
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    }
    
    .message.success {
        background-color: #4CAF50;
    }
    
    .message.error {
        background-color: #f44336;
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .table-actions {
        display: flex;
        gap: 10px;
    }
`;
document.head.appendChild(messageStyle);

// Styling aktualisieren
const style = document.createElement('style');
style.textContent = `
    .attribute-tables-container {
        display: flex;
        flex-direction: column;
        gap: 30px;
        padding: 20px;
    }
    .table-container {
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 20px;
    }
    .table-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    .toggle-columns-btn {
        background: #2c5530;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
    }
    .toggle-columns-btn:hover {
        background: #1e3c21;
    }
    .column-dropdown {
        background: white;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 15px;
        display: none;
    }
    .column-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 8px;
        cursor: pointer;
    }
    .column-checkbox:hover {
        background: #f5f5f5;
    }
    .attribute-table {
        width: 100%;
        border-collapse: collapse;
    }
    .attribute-table th, .attribute-table td {
        padding: 12px;
        border: 1px solid #ddd;
        text-align: left;
    }
    .attribute-table th {
        background-color: #f5f5f5;
        font-weight: 600;
    }
    .attribute-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    .hidden-column {
        display: none;
    }
`;
document.head.appendChild(style);

async function showAttributeViewer(wfsUrl, layerName) {
    try {
        const formData = new FormData();
        formData.append('wfs_url', wfsUrl);
        formData.append('layer_name', layerName);

        const response = await fetch('/get_attributes', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            showError('Fehler beim Laden der Attributtabelle: ' + data.message);
            return;
        }

        // Container für die Attribut-Ansicht
        const modalContent = document.createElement('div');
        modalContent.className = 'attribute-viewer-container';
        
        // Header mit Titel und Aktionen
        const header = document.createElement('div');
        header.className = 'viewer-header';
        
        const title = document.createElement('h2');
        title.textContent = 'Attribute: ' + layerName;
        header.appendChild(title);
        
        // Aktions-Container
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'viewer-actions';
        
        // Sync-Button nur für ATKIS-Layer
        if (layerName.startsWith('ax_')) {
            const syncButton = document.createElement('button');
            syncButton.className = 'action-btn sync-btn';
            syncButton.innerHTML = '<i class="bi bi-sync"></i> Werte synchronisieren';
            syncButton.onclick = () => synchronizeValues(data, layerName, modalContent);
            actionsContainer.appendChild(syncButton);
        }
        
        // Download-Button
        const downloadButton = document.createElement('button');
        downloadButton.className = 'action-btn download-btn';
        downloadButton.innerHTML = '<i class="bi bi-download"></i> Auswahl herunterladen';
        downloadButton.onclick = () => downloadSelectedFeatures();
        actionsContainer.appendChild(downloadButton);
        
        header.appendChild(actionsContainer);
        modalContent.appendChild(header);
        
        // Daten-Container
        const dataContainer = document.createElement('div');
        dataContainer.className = 'data-container';
        
        // Spaltenauswahl
        const columnSelector = createColumnSelector(data.attributes);
        dataContainer.appendChild(columnSelector);
        
        // Tabellen-Container
        const tablesContainer = document.createElement('div');
        tablesContainer.className = 'tables-container';
        
        // Original Tabelle
        const originalTable = createFeatureTable(
            data.attributes,
            false,
            data.is_atkis
        );
        tablesContainer.appendChild(originalTable);
        
        dataContainer.appendChild(tablesContainer);
        
        // Paginierung
        const pagination = createPagination();
        dataContainer.appendChild(pagination);
        
        modalContent.appendChild(dataContainer);
        
        // Styling
        const style = document.createElement('style');
        style.textContent = `
            .attribute-viewer-container {
                display: flex;
                flex-direction: column;
                gap: 20px;
                padding: 20px;
                height: 100%;
            }
            
            .viewer-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 20px;
                background: #f5f5f5;
                border-radius: 8px;
            }
            
            .viewer-actions {
                display: flex;
                gap: 10px;
            }
            
            .action-btn {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                color: white;
                background: #2c5530;
            }
            
            .action-btn:hover {
                background: #1e3c21;
            }
            
            .action-btn:disabled {
                background: #cccccc;
                cursor: not-allowed;
            }
            
            .data-container {
                display: flex;
                flex-direction: column;
                gap: 20px;
                flex: 1;
                overflow: hidden;
            }
            
            .tables-container {
                flex: 1;
                overflow: auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .pagination {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 10px;
                padding: 10px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .pagination button {
                padding: 5px 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                cursor: pointer;
            }
            
            .pagination button:hover {
                background: #f5f5f5;
            }
            
            .pagination button:disabled {
                background: #f5f5f5;
                cursor: not-allowed;
            }
            
            .pagination .current-page {
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
        
        // Modal anzeigen
        showModal('Attribut-Viewer', modalContent);
        
    } catch (error) {
        console.error('Fehler beim Laden der Attribute:', error);
        showError('Fehler beim Laden der Attribute: ' + error.message);
    }
}

function createColumnSelector(attributes) {
    const container = document.createElement('div');
    container.className = 'column-selector';
    
    const title = document.createElement('h3');
    title.textContent = 'Spalten auswählen';
    container.appendChild(title);
    
    const checkboxContainer = document.createElement('div');
    checkboxContainer.className = 'checkbox-container';
    
    Object.keys(attributes).forEach(columnName => {
        const label = document.createElement('label');
        label.className = 'column-checkbox';
        label.innerHTML = `
            <input type="checkbox" checked data-column="${columnName}">
            <span>${columnName}</span>
        `;
        checkboxContainer.appendChild(label);
    });
    
    container.appendChild(checkboxContainer);
    return container;
}

function createFeatureTable(attributes, translated = false, isAtkis = false) {
    const container = document.createElement('div');
    container.className = 'feature-table-container';
    
    const table = document.createElement('table');
    table.className = 'feature-table';
    
    // Kopfzeile
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    // Checkbox für "Alle auswählen"
    const selectAllHeader = document.createElement('th');
    const selectAllCheckbox = document.createElement('input');
    selectAllCheckbox.type = 'checkbox';
    selectAllCheckbox.className = 'select-all-checkbox';
    selectAllHeader.appendChild(selectAllCheckbox);
    headerRow.appendChild(selectAllHeader);
    
    Object.keys(attributes).forEach(columnName => {
        const th = document.createElement('th');
        th.textContent = columnName;
        th.dataset.column = columnName;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Tabelleninhalt
    const tbody = document.createElement('tbody');
    table.appendChild(tbody);
    
    container.appendChild(table);
    return container;
}

function createPagination() {
    const container = document.createElement('div');
    container.className = 'pagination';
    
    const prevButton = document.createElement('button');
    prevButton.innerHTML = '&larr;';
    prevButton.className = 'prev-btn';
    container.appendChild(prevButton);
    
    const pageInfo = document.createElement('span');
    pageInfo.className = 'current-page';
    pageInfo.textContent = 'Seite 1 von 1';
    container.appendChild(pageInfo);
    
    const nextButton = document.createElement('button');
    nextButton.innerHTML = '&rarr;';
    nextButton.className = 'next-btn';
    container.appendChild(nextButton);
    
    return container;
}

async function synchronizeValues(data, layerName, container) {
    try {
        const syncButton = container.querySelector('.sync-btn');
        syncButton.disabled = true;
        syncButton.innerHTML = '<i class="bi bi-sync"></i> Synchronisiere...';
        
        const response = await fetch('/sync_atkis_names', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                attributes: data.attributes,
                layer_name: layerName
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'error') {
            throw new Error(result.message);
        }
        
        // Aktualisiere die Tabellen
        const tablesContainer = container.querySelector('.tables-container');
        tablesContainer.innerHTML = '';
        
        const originalTable = createFeatureTable(
            result.attributes,
            false,
            true
        );
        tablesContainer.appendChild(originalTable);
        
        const translatedTable = createFeatureTable(
            result.attributes,
            true,
            true
        );
        tablesContainer.appendChild(translatedTable);
        
        showMessage('Werte erfolgreich synchronisiert');
        
    } catch (error) {
        console.error('Synchronisierungsfehler:', error);
        showError('Fehler bei der Synchronisierung: ' + error.message);
    } finally {
        const syncButton = container.querySelector('.sync-btn');
        syncButton.disabled = false;
        syncButton.innerHTML = '<i class="bi bi-sync"></i> Werte synchronisieren';
    }
}

// Event-Listener für den neuen Attribut-Viewer-Button
document.addEventListener('DOMContentLoaded', () => {
    const viewerButtons = document.querySelectorAll('.show-attributes-btn');
    viewerButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const wfsUrl = e.target.dataset.wfsUrl;
            const layerName = e.target.dataset.layerName;
            showAttributeViewer(wfsUrl, layerName);
        });
    });
});

function displayLayers(data) {
    const layerList = document.getElementById('layer-list');
    layerList.innerHTML = '';
    
    // Globale ATKIS-Checkbox am Anfang
    const globalAtkisContainer = document.createElement('div');
    globalAtkisContainer.className = 'global-atkis-container';
    
    const globalAtkisCheckbox = document.createElement('input');
    globalAtkisCheckbox.type = 'checkbox';
    globalAtkisCheckbox.id = 'global-atkis';
    globalAtkisCheckbox.className = 'atkis-checkbox';
    
    const globalAtkisLabel = document.createElement('label');
    globalAtkisLabel.htmlFor = 'global-atkis';
    globalAtkisLabel.textContent = 'Alle Layer als ATKIS-Layer markieren';
    
    globalAtkisContainer.appendChild(globalAtkisCheckbox);
    globalAtkisContainer.appendChild(globalAtkisLabel);
    layerList.appendChild(globalAtkisContainer);
    
    // Event-Listener für die globale ATKIS-Checkbox
    globalAtkisCheckbox.addEventListener('change', (e) => {
        const allSyncButtons = document.querySelectorAll('.sync-names-btn');
        allSyncButtons.forEach(button => {
            button.style.display = e.target.checked ? 'inline-flex' : 'none';
        });
    });
    
    Object.entries(data.layers).forEach(([namespace, layers]) => {
        const namespaceDiv = document.createElement('div');
        namespaceDiv.className = 'namespace-group';
        
        const namespaceTitle = document.createElement('h3');
        namespaceTitle.textContent = namespace;
        namespaceDiv.appendChild(namespaceTitle);
        
        Object.entries(layers).forEach(([layerName, layerInfo]) => {
            const layerDiv = document.createElement('div');
            layerDiv.className = 'layer-item';
            
            const layerTitle = document.createElement('h4');
            layerTitle.textContent = layerInfo.title;
            layerDiv.appendChild(layerTitle);
            
            // Button-Container
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'button-container';
            
            // Download Button
            const downloadButton = document.createElement('button');
            downloadButton.className = 'action-btn download-btn';
            downloadButton.innerHTML = '<i class="bi bi-download"></i> Download';
            downloadButton.onclick = () => prepareDownload(data.wfs_url, layerInfo.name, layerInfo.title);
            buttonContainer.appendChild(downloadButton);
            
            // Attribute einsehen Button
            const viewButton = document.createElement('button');
            viewButton.className = 'action-btn view-attributes-btn';
            viewButton.innerHTML = '<i class="bi bi-table"></i> Attribute einsehen';
            viewButton.onclick = () => showAttributeViewer(data.wfs_url, layerInfo.name);
            buttonContainer.appendChild(viewButton);
            
            // Attributtabelle bearbeiten Button
            const editButton = document.createElement('button');
            editButton.className = 'action-btn edit-attributes-btn';
            editButton.innerHTML = '<i class="bi bi-pencil"></i> Attributtabelle bearbeiten';
            editButton.onclick = () => showAttributeEditor(data.wfs_url, layerInfo.name);
            buttonContainer.appendChild(editButton);
            
            // Namen synchronisieren Button (initial versteckt)
            const syncButton = document.createElement('button');
            syncButton.className = 'action-btn sync-names-btn';
            syncButton.innerHTML = '<i class="bi bi-sync"></i> Namen synchronisieren';
            syncButton.style.display = 'none';
            syncButton.onclick = () => synchronizeNames(data.wfs_url, layerInfo.name);
            buttonContainer.appendChild(syncButton);
            
            layerDiv.appendChild(buttonContainer);
            namespaceDiv.appendChild(layerDiv);
        });
        
        layerList.appendChild(namespaceDiv);
    });
}

// Styling für die Layer-Liste und Buttons
const style = document.createElement('style');
style.textContent = `
    .global-atkis-container {
        background: #f0f8ff;
        padding: 15px;
        margin: 20px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .global-atkis-container label {
        font-weight: 500;
        color: #333;
        cursor: pointer;
        font-size: 16px;
    }
    
    .global-atkis-container input[type="checkbox"] {
        width: 20px;
        height: 20px;
        cursor: pointer;
    }
    
    .button-container {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 10px;
    }
    
    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        color: white;
        min-width: 160px;
        justify-content: center;
        transition: all 0.3s ease;
    }
    
    .download-btn {
        background: #2c5530;
    }
    
    .view-attributes-btn {
        background: #4a90e2;
    }
    
    .edit-attributes-btn {
        background: #f5a623;
    }
    
    .sync-names-btn {
        background: #7ed321;
    }
    
    .action-btn:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
    
    .layer-item {
        background: white;
        border-radius: 8px;
        padding: 15px;
        margin: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .layer-item h4 {
        margin: 0 0 10px 0;
        color: #2c5530;
        font-size: 16px;
    }
    
    .namespace-group {
        margin: 20px;
        padding: 10px;
        background: #f8f9fa;
        border-radius: 8px;
    }
    
    .namespace-group h3 {
        color: #333;
        margin: 0 0 15px 0;
        padding: 10px;
        border-bottom: 2px solid #2c5530;
        font-size: 18px;
    }
`;
document.head.appendChild(style);

// Hilfsfunktion für den Download
async function prepareDownload(wfsUrl, layerName, layerTitle) {
    try {
        const formData = new FormData();
        formData.append('wfs_url', wfsUrl);
        formData.append('layer_name', layerName);
        formData.append('layer_title', layerTitle);
        formData.append('format', 'SHAPEFILE');
        
        const response = await fetch('/prepare_download', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${layerTitle.replace(/[^a-z0-9äöüß\s-]/gi, '_')}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showMessage('Download erfolgreich');
        
    } catch (error) {
        console.error('Download-Fehler:', error);
        showError('Fehler beim Download: ' + error.message);
    }
}

// Hilfsfunktion für die Namens-Synchronisierung
async function synchronizeNames(wfsUrl, layerName) {
    try {
        const isAtkis = document.getElementById('global-atkis').checked;
        
        const response = await fetch('/sync_atkis_names', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                layer_name: layerName,
                is_atkis: isAtkis
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            showMessage('Namen erfolgreich synchronisiert');
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        console.error('Synchronisierungsfehler:', error);
        showError('Fehler bei der Synchronisierung: ' + error.message);
    }
}

async function showAttributeEditor(wfsUrl, layerName) {
    try {
        const formData = new FormData();
        formData.append('wfs_url', wfsUrl);
        formData.append('layer_name', layerName);

        const response = await fetch('/get_attributes', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            showError('Fehler beim Laden der Attributtabelle: ' + data.message);
            return;
        }

        // Container für den Attribut-Editor
        const modalContent = document.createElement('div');
        modalContent.className = 'attribute-editor-container';
        
        // Header mit Titel und Aktionen
        const header = document.createElement('div');
        header.className = 'editor-header';
        
        const title = document.createElement('h2');
        title.textContent = 'Attributtabelle bearbeiten: ' + layerName;
        header.appendChild(title);
        
        // Aktions-Container
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'editor-actions';
        
        // Speichern Button
        const saveButton = document.createElement('button');
        saveButton.className = 'action-btn save-btn';
        saveButton.innerHTML = '<i class="bi bi-save"></i> Änderungen speichern';
        saveButton.onclick = () => saveAttributeChanges(wfsUrl, layerName);
        actionsContainer.appendChild(saveButton);
        
        header.appendChild(actionsContainer);
        modalContent.appendChild(header);
        
        // Attribut-Editor-Tabelle
        const editorTable = createAttributeEditorTable(data.features, data.attribute_info);
        modalContent.appendChild(editorTable);
        
        // Styling
        const style = document.createElement('style');
        style.textContent = `
            .attribute-editor-container {
                display: flex;
                flex-direction: column;
                gap: 20px;
                padding: 20px;
                height: 100%;
            }
            
            .editor-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 15px;
                background: #f5f5f5;
                border-radius: 8px;
            }
            
            .editor-actions {
                display: flex;
                gap: 10px;
            }
            
            .save-btn {
                background: #4CAF50;
            }
            
            .save-btn:hover {
                background: #45a049;
            }
            
            .attribute-editor-table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .attribute-editor-table th,
            .attribute-editor-table td {
                padding: 12px;
                border: 1px solid #ddd;
            }
            
            .attribute-editor-table th {
                background: #f5f5f5;
                font-weight: 600;
                text-align: left;
            }
            
            .attribute-editor-table td input {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            
            .attribute-editor-table td input:focus {
                outline: none;
                border-color: #4a90e2;
                box-shadow: 0 0 0 2px rgba(74,144,226,0.2);
            }
        `;
        document.head.appendChild(style);
        
        // Modal anzeigen
        showModal('Attribut-Editor', modalContent);
        
    } catch (error) {
        console.error('Fehler beim Laden des Attribut-Editors:', error);
        showError('Fehler beim Laden des Attribut-Editors: ' + error.message);
    }
}

function createAttributeEditorTable(features, attributeInfo) {
    const table = document.createElement('table');
    table.className = 'attribute-editor-table';
    
    // Tabellenkopf
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    // Checkbox für "Alle auswählen"
    const selectAllHeader = document.createElement('th');
    const selectAllCheckbox = document.createElement('input');
    selectAllCheckbox.type = 'checkbox';
    selectAllCheckbox.className = 'select-all-checkbox';
    selectAllHeader.appendChild(selectAllCheckbox);
    headerRow.appendChild(selectAllHeader);
    
    // Spaltenüberschriften
    Object.keys(attributeInfo).forEach(columnName => {
        const th = document.createElement('th');
        th.textContent = columnName;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Tabelleninhalt
    const tbody = document.createElement('tbody');
    features.forEach((feature, index) => {
        const row = document.createElement('tr');
        
        // Checkbox für Zeilenauswahl
        const checkboxCell = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'row-checkbox';
        checkbox.dataset.rowIndex = index;
        checkboxCell.appendChild(checkbox);
        row.appendChild(checkboxCell);
        
        // Attributwerte
        Object.entries(feature).forEach(([key, value]) => {
            const cell = document.createElement('td');
            const input = document.createElement('input');
            input.type = 'text';
            input.value = value;
            input.dataset.column = key;
            input.dataset.rowIndex = index;
            cell.appendChild(input);
            row.appendChild(cell);
        });
        
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    
    // Event-Listener für "Alle auswählen" Checkbox
    selectAllCheckbox.addEventListener('change', (e) => {
        const checkboxes = tbody.querySelectorAll('.row-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = e.target.checked;
        });
    });
    
    return table;
}

async function saveAttributeChanges(wfsUrl, layerName) {
    try {
        const table = document.querySelector('.attribute-editor-table');
        const selectedRows = table.querySelectorAll('.row-checkbox:checked');
        
        if (selectedRows.length === 0) {
            showError('Bitte wählen Sie mindestens eine Zeile aus');
            return;
        }
        
        const changes = [];
        selectedRows.forEach(checkbox => {
            const rowIndex = checkbox.dataset.rowIndex;
            const row = table.querySelector(`tr:nth-child(${parseInt(rowIndex) + 2})`);
            const inputs = row.querySelectorAll('input[type="text"]');
            
            const rowChanges = {};
            inputs.forEach(input => {
                rowChanges[input.dataset.column] = input.value;
            });
            
            changes.push(rowChanges);
        });
        
        const response = await fetch('/save_attribute_changes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                wfs_url: wfsUrl,
                layer_name: layerName,
                changes: changes
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.status === 'success') {
            showMessage('Änderungen erfolgreich gespeichert');
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        console.error('Fehler beim Speichern der Änderungen:', error);
        showError('Fehler beim Speichern der Änderungen: ' + error.message);
    }
} 