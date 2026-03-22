function showLoadingOverlay(id) {
    const overlay = document.getElementById(id);
    if (!overlay) return;
    overlay.classList.remove('px-loading-overlay--hiding');
    overlay.classList.add('px-loading-overlay--visible');
}

function hideLoadingOverlay(id) {
    const overlay = document.getElementById(id);
    if (!overlay) return;
    overlay.classList.add('px-loading-overlay--hiding');
    overlay.addEventListener('animationend', () => {
        overlay.classList.remove('px-loading-overlay--visible', 'px-loading-overlay--hiding');
    }, { once: true });
}
