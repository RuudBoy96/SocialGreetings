(function initCardAvatar() {
    const dataEl = document.getElementById('card-data');
    const fileInput = document.getElementById('avatar-file-input');
    const uploadBtn = document.getElementById('btn-add-avatar');
    if (!dataEl || !fileInput || !uploadBtn) return;

    const cardData = JSON.parse(dataEl.textContent);
    const cardId = cardData.card_id;

    if (cardData.contact_avatar) {
        uploadBtn.textContent = 'Change contact photo';
    }

    uploadBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files?.[0];
        if (!file) return;

        const allowed = ['image/jpeg', 'image/png', 'image/webp'];
        if (!allowed.includes(file.type)) {
            alert('Please choose a JPEG, PNG, or WebP image.');
            fileInput.value = '';
            return;
        }
        if (file.size > 500 * 1024) {
            alert('Image must be 500 KB or smaller.');
            fileInput.value = '';
            return;
        }

        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading…';

        const formData = new FormData();
        formData.append('avatar', file);

        try {
            const res = await fetch(`/api/card/${cardId}/avatar`, {
                method: 'POST',
                body: formData,
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            document.querySelectorAll('.chat-header .header-avatar').forEach((avatarEl) => {
                let img = avatarEl.querySelector('.header-avatar-img');
                if (!img) {
                    avatarEl.innerHTML = '';
                    img = document.createElement('img');
                    img.className = 'header-avatar-img';
                    img.alt = '';
                    avatarEl.appendChild(img);
                }
                img.src = data.contact_avatar;
            });

            uploadBtn.textContent = 'Change contact photo';
        } catch (err) {
            alert(err.message || 'Could not upload photo. Please try again.');
            uploadBtn.textContent = cardData.contact_avatar ? 'Change contact photo' : 'Add contact photo';
        } finally {
            uploadBtn.disabled = false;
            fileInput.value = '';
        }
    });
})();
