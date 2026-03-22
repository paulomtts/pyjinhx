function openPxDrawer(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.showModal();
}

function closePxDrawer(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('px-drawer--closing');
    el.addEventListener(
        'animationend',
        () => {
            el.classList.remove('px-drawer--closing');
            el.close();
        },
        { once: true }
    );
}

document.addEventListener('click', (e) => {
    if (e.target.tagName === 'DIALOG' && e.target.classList.contains('px-drawer')) {
        closePxDrawer(e.target.id);
    }
});
