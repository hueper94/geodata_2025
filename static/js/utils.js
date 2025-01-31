// Hilfsfunktionen für Nachrichten und UI
export function showError(message) {
    const notification = document.getElementById('notification');
    if (notification) {
        notification.textContent = message;
        notification.className = 'alert alert-danger';
        notification.style.display = 'block';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 5000);
    }
    console.error('Fehler:', message);
}

export function showSuccess(message) {
    const notification = document.getElementById('notification');
    if (notification) {
        notification.textContent = message;
        notification.className = 'alert alert-success';
        notification.style.display = 'block';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }
    console.log('Erfolg:', message);
}

export function showLoadingOverlay(show, status = '', details = '') {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingStatus = document.getElementById('loadingStatus');
    const loadingDetails = document.getElementById('loadingDetails');
    
    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
        if (show && loadingStatus) {
            loadingStatus.textContent = status || 'Lädt...';
        }
        if (show && loadingDetails) {
            loadingDetails.textContent = details;
        }
    }
    
    if (show) {
        console.log('Loading:', status, details ? `(${details})` : '');
    }
} 