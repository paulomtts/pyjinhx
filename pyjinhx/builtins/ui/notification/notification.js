const _notificationTimers = {};

function showNotification(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('px-notification--hiding');
    el.classList.add('px-notification--visible');

    clearTimeout(_notificationTimers[id]);
    const timeout = parseInt(el.dataset.timeout, 10);
    if (timeout > 0) {
        _notificationTimers[id] = setTimeout(() => hideNotification(id), timeout);
    }
}

function hideNotification(id) {
    const el = document.getElementById(id);
    if (!el || !el.classList.contains('px-notification--visible')) return;
    el.classList.add('px-notification--hiding');
    el.addEventListener('animationend', () => {
        el.classList.remove('px-notification--visible', 'px-notification--hiding');
    }, { once: true });
}
