function togglePxDropdown(id) {
    const root = document.getElementById(id);
    if (!root) return;
    const menu = document.getElementById(id + '-menu');
    const trigger = document.getElementById(id + '-trigger');
    if (!menu || !trigger) return;
    const open = menu.hasAttribute('hidden');
    if (open) {
        menu.removeAttribute('hidden');
        menu.classList.add('px-dropdown__menu--open');
        trigger.setAttribute('aria-expanded', 'true');
    } else {
        closePxDropdown(id);
    }
}

function closePxDropdown(id) {
    const root = document.getElementById(id);
    if (!root) return;
    const menu = document.getElementById(id + '-menu');
    const trigger = document.getElementById(id + '-trigger');
    if (menu) {
        menu.setAttribute('hidden', '');
        menu.classList.remove('px-dropdown__menu--open');
    }
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
}

document.addEventListener('click', (e) => {
    document.querySelectorAll('.px-dropdown').forEach((root) => {
        const menu = root.querySelector('.px-dropdown__menu');
        if (menu && !menu.hasAttribute('hidden') && !root.contains(e.target)) {
            closePxDropdown(root.id);
        }
    });
});

document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.px-dropdown').forEach((root) => {
        const menu = root.querySelector('.px-dropdown__menu');
        if (menu && !menu.hasAttribute('hidden')) closePxDropdown(root.id);
    });
});
