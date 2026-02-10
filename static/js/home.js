document.addEventListener('DOMContentLoaded', function () {
    const modalElement = document.getElementById('modalPrioridad');
    if (!modalElement) return;

    const bsModal = new bootstrap.Modal(modalElement);
    const imgContainer = document.getElementById('prioridadImageContainer');
    const imgElement = document.getElementById('prioridadImg');

    // Usamos la URL que pasamos desde el HTML
    fetch(window.PriorityConfig.checkUrl)
        .then(response => response.json())
        .then(data => {
            if (data.has_priority) {
                // 1. Cargar Texto
                document.getElementById('prioridadMessage').innerText = data.message;
                document.getElementById('prioridadHeader').style.backgroundColor = data.color;
                modalElement.setAttribute('data-announcement-id', data.id);

                // 2. Cargar Imagen (Si existe)
                if (data.image_url) {
                    imgElement.src = data.image_url;
                    imgContainer.classList.remove('d-none');
                } else {
                    imgContainer.classList.add('d-none');
                }

                bsModal.show();
            }
        });

    document.getElementById('btnAceptarPrioridad').addEventListener('click', function () {
        const announcementId = modalElement.getAttribute('data-announcement-id');
        this.disabled = true;

        // Usamos el Token que pasamos desde el HTML
        fetch(`/recognitions/api/mark-read/${announcementId}/`, {
            method: 'POST',
            headers: { 
                'X-CSRFToken': window.PriorityConfig.csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then(response => {
            if (response.ok) {
                bsModal.hide();
            } else {
                this.disabled = false;
            }
        });
    });
});