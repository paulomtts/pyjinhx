function dismissPxAlert(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('px-alert--dismissed');
}
