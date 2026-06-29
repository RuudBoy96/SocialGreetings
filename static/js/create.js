document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('chat_file');
    const uploadZone = document.getElementById('upload-zone');
    const filenameEl = document.getElementById('upload-filename');
    const optionsSection = document.getElementById('options-section');
    const submitBtn = document.getElementById('submit-btn');
    const cardForSelect = document.getElementById('card_for');
    const contactNameInput = document.getElementById('contact_name');
    const platformSelect = document.getElementById('platform');
    const platformHint = document.getElementById('platform-hint');

    if (!fileInput) return;

    fileInput.addEventListener('change', () => handleFile(fileInput.files[0]));

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFile(e.dataTransfer.files[0]);
        }
    });

    let cachedParticipants = [];

    if (cardForSelect) {
        cardForSelect.addEventListener('change', () => {
            const selected = cardForSelect.value;
            if (selected && cachedParticipants.length === 2 && contactNameInput) {
                const other = cachedParticipants.find((p) => p !== selected);
                if (other) contactNameInput.value = other;
            }
        });
    }

    async function handleFile(file) {
        if (!file) return;

        filenameEl.textContent = file.name;
        if (submitBtn) submitBtn.disabled = false;
        if (optionsSection) optionsSection.hidden = false;

        const contactFromFilename = extractContactFromFilename(file.name);
        if (contactFromFilename && contactNameInput && !contactNameInput.value) {
            contactNameInput.placeholder = contactFromFilename;
        }

        try {
            const formData = new FormData();
            formData.append('chat_file', file);
            if (platformSelect) formData.append('platform', platformSelect.value);

            const response = await fetch('/api/preview-participants', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            populateParticipants(data.participants, data.contact_name);

            if (data.platform && platformHint) {
                const names = { whatsapp: 'WhatsApp', imessage: 'iMessage', messenger: 'Messenger' };
                platformHint.textContent = `Detected: ${names[data.platform] || data.platform}`;
            }
        } catch {
            /* preview is optional */
        }
    }

    function populateParticipants(participants, contactName) {
        if (!cardForSelect) return;
        cachedParticipants = participants;
        cardForSelect.innerHTML = '<option value="">Auto-detect from chat</option>';

        participants.forEach((name) => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            cardForSelect.appendChild(option);
        });

        if (contactNameInput) {
            if (contactName && !contactNameInput.value) {
                contactNameInput.value = contactName;
            } else if (participants.length === 2 && !contactNameInput.value) {
                contactNameInput.placeholder = participants[1];
            }
        }
    }

    function extractContactFromFilename(filename) {
        const patterns = [
            /WhatsApp Chat with (.+)\.txt$/i,
            /iMessage Chat with (.+)\.txt$/i,
            /Messenger Chat with (.+)\.txt$/i,
            /Facebook Message History with (.+)\.txt$/i,
            /Messages - (.+)\.txt$/i,
        ];
        for (const p of patterns) {
            const match = filename.match(p);
            if (match) return match[1].trim();
        }
        return '';
    }
});
