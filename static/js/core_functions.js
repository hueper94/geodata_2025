// Core-Funktionen für den WFS/WMS Explorer
// Diese Funktionen sind essentiell und sollten nicht verändert werden

// Download-Funktionalität
async function downloadLayer(wfsUrl, layerName, layerTitle, format) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('wfs_url', wfsUrl);
        formData.append('layer_name', layerName);
        formData.append('format', format);
        formData.append('layer_title', layerTitle);
        
        fetch('/prepare_download', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Netzwerk-Antwort war nicht ok');
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json().then(data => {
                    throw new Error(data.message || 'Unbekannter Fehler beim Download');
                });
            }
            
            return response.blob();
        })
        .then(blob => {
            if (blob.size === 0) {
                throw new Error('Die heruntergeladene Datei ist leer');
            }
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const safeTitle = layerTitle.replace(/[^a-z0-9äöüß\s-]/gi, '_').trim();
            a.download = `${safeTitle}.${format.toLowerCase()}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            resolve();
        })
        .catch(reject);
    });
}

// Mehrfach-Download Funktionalität
async function downloadSelectedLayers() {
    const selectedLayers = document.querySelectorAll('.layer-checkbox:checked');
    const format = document.getElementById('download-format').value;
    const totalLayers = selectedLayers.length;
    let successCount = 0;
    
    if (totalLayers === 0) {
        showNotification('Bitte wählen Sie mindestens einen Layer aus', 'error');
        return;
    }
    
    showLoadingSpinner('Starte Download der ausgewählten Layer...');
    
    for (let i = 0; i < totalLayers; i++) {
        const checkbox = selectedLayers[i];
        const layerName = checkbox.dataset.layerName;
        const wfsUrl = checkbox.dataset.wfsUrl;
        const row = checkbox.closest('tr');
        const layerTitle = row.cells[1].textContent.trim();
        
        showLoadingSpinner(`Lade Layer ${i + 1} von ${totalLayers}: ${layerTitle}`);
        
        try {
            await downloadLayer(wfsUrl, layerName, layerTitle, format);
            checkbox.checked = false;
            updateDownloadButtonVisibility();
            showNotification(`Download von "${layerTitle}" abgeschlossen`, 'success');
            successCount++;
        } catch (error) {
            showNotification(`Fehler beim Download von "${layerTitle}": ${error.message}`, 'error');
        }
    }
    
    hideLoadingSpinner();
    document.getElementById('select-all-layers').checked = false;
    updateDownloadButtonVisibility();
    
    if (successCount > 0) {
        if (successCount === totalLayers) {
            showNotification(`Alle ${totalLayers} Downloads erfolgreich abgeschlossen`, 'success');
        } else {
            showNotification(`${successCount} von ${totalLayers} Downloads erfolgreich abgeschlossen`, 'warning');
        }
    }
}

// Hilfsfunktionen für die UI
function updateDownloadButtonVisibility() {
    const container = document.getElementById('download-selected-container');
    const selectedCount = document.querySelectorAll('.layer-checkbox:checked').length;
    container.style.display = selectedCount > 0 ? 'block' : 'none';
}

function showLoadingSpinner(message) {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingStatus = document.getElementById('loadingStatus');
    loadingOverlay.style.display = 'flex';
    loadingStatus.textContent = message;
}

function hideLoadingSpinner() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    loadingOverlay.style.display = 'none';
    if (abortController) {
        abortController = null;
    }
}

function showNotification(message, type) {
    const notification = document.getElementById('notification');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type}`;
    notification.innerHTML = message;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
} 