const MIN_FONT_SIZE = 2.5;
const START_FONT_SIZE = 11;
const MIN_GAP = 0.5;
const START_GAP = 2;
const OVERFLOW_SPLIT_THRESHOLD = 120;

document.addEventListener('DOMContentLoaded', () => {
    const dataEl = document.getElementById('card-data');
    if (!dataEl) return;

    const cardData = JSON.parse(dataEl.textContent);
    renderCard(cardData);
});

function renderCard(cardData) {
    const receiverName = cardData.receiver_name;
    const splitRequested = cardData.split_pages;
    const things = cardData.things || [];
    const eachOther = cardData.each_other || [];
    const allMessages = cardData.messages || [];

    let page1Messages = allMessages;
    let page2Messages = [];
    let showPage2 = false;

    if (splitRequested && eachOther.length > 0 && things.length > 0) {
        page1Messages = things;
        page2Messages = eachOther;
        showPage2 = true;
    }

    renderMessages('chat-page-1', page1Messages, receiverName);
    const page1Overflow = shrinkToFit(document.getElementById('chat-page-1'));

    if (!showPage2 && (page1Overflow || allMessages.length > OVERFLOW_SPLIT_THRESHOLD) && eachOther.length > 0) {
        page1Messages = things.length > 0 ? things : allMessages.filter(m => m.category !== 'each_other');
        page2Messages = eachOther;
        showPage2 = page2Messages.length > 0;
    }

    if (showPage2) {
        if (page1Messages !== allMessages) {
            renderMessages('chat-page-1', page1Messages, receiverName);
            shrinkToFit(document.getElementById('chat-page-1'));
        }

        const slidePage2 = document.getElementById('carousel-slide-2');
        const page2El = document.getElementById('chat-page-2');

        if (slidePage2) {
            slidePage2.classList.add('is-visible');
        }

        if (page2El) {
            prepareHiddenLayout(page2El);
            renderMessages('chat-page-2', page2Messages, receiverName);
            const page2Opts = {
                startFontSize: page2Messages.length > page1Messages.length ? START_FONT_SIZE * 0.82 : START_FONT_SIZE * 0.9,
            };
            shrinkToFit(page2El, page2Opts);
            clearHiddenLayout(page2El);
        }
    }

    window.dispatchEvent(new CustomEvent('card-render-complete', {
        detail: { showPage2 },
    }));
}

function prepareHiddenLayout(chatBody) {
    if (!chatBody) return;
    chatBody.style.visibility = 'hidden';
    chatBody.style.position = 'absolute';
    chatBody.style.left = '0';
    chatBody.style.right = '0';
    chatBody.style.top = '0';
    chatBody.style.height = chatBody.parentElement?.clientHeight
        ? `${chatBody.parentElement.clientHeight - 50}px`
        : '100%';
}

function clearHiddenLayout(chatBody) {
    if (!chatBody) return;
    chatBody.style.visibility = '';
    chatBody.style.position = '';
    chatBody.style.left = '';
    chatBody.style.right = '';
    chatBody.style.top = '';
    chatBody.style.height = '';
}

function renderMessages(containerId, messages, receiverName) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    messages.forEach(msg => {
        const bubble = document.createElement('div');
        const isSent = msg.sender === receiverName;
        bubble.className = `message ${isSent ? 'sent' : 'received'}`;
        bubble.innerHTML = `
            <span class="message-text">${escapeHtml(msg.message)}</span><span class="timestamp">${escapeHtml(msg.time_display)}</span>
        `;
        container.appendChild(bubble);
    });
}

function shrinkToFit(chatBody, options = {}) {
    if (!chatBody) return false;

    const startFontSize = options.startFontSize ?? START_FONT_SIZE;
    let currentSize = startFontSize;
    let currentGap = START_GAP;

    chatBody.style.fontSize = currentSize + 'px';
    chatBody.style.gap = currentGap + 'px';
    chatBody.style.padding = '5px 7px 8px 7px';

    while (chatBody.scrollHeight > chatBody.clientHeight && currentSize > MIN_FONT_SIZE) {
        currentSize -= 0.12;
        chatBody.style.fontSize = currentSize + 'px';
    }

    while (chatBody.scrollHeight > chatBody.clientHeight && currentGap > MIN_GAP) {
        currentGap -= 0.2;
        chatBody.style.gap = currentGap + 'px';
    }

    while (chatBody.scrollHeight > chatBody.clientHeight && currentSize > MIN_FONT_SIZE) {
        currentSize -= 0.08;
        chatBody.style.fontSize = currentSize + 'px';
    }

    if (chatBody.scrollHeight > chatBody.clientHeight) {
        currentGap = MIN_GAP;
        chatBody.style.gap = currentGap + 'px';
        while (chatBody.scrollHeight > chatBody.clientHeight && currentSize > MIN_FONT_SIZE) {
            currentSize -= 0.05;
            chatBody.style.fontSize = currentSize + 'px';
        }
    }

    return currentSize <= MIN_FONT_SIZE && chatBody.scrollHeight > chatBody.clientHeight;
}

function fitChatPage(chatBody, options = {}) {
    shrinkToFit(chatBody, options);
}

window.refitChatPage = (chatBody, options = {}) => fitChatPage(chatBody, options);

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
