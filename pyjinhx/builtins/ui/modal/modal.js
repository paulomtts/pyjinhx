function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.showModal();
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('px-modal--closing');
    modal.addEventListener('animationend', () => {
        modal.classList.remove('px-modal--closing');
        modal.close();
    }, { once: true });
}

// Close on backdrop click (click lands on the <dialog> element itself,
// not on any child, when the user clicks outside the modal box)
document.addEventListener('click', (e) => {
    if (e.target.tagName === 'DIALOG') {
        closeModal(e.target.id);
    }
});
