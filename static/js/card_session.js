// Keeps a card alive while its page is open (heartbeat), and wires up any
// "Delete my card now" buttons. The card id is read from a <meta name="card-id">.
(function () {
    const meta = document.querySelector('meta[name="card-id"]');
    const cardId = meta && meta.content;
    if (!cardId) return;

    const PING_INTERVAL_MS = 2 * 60 * 1000;

    function ping() {
        if (document.hidden) return;
        fetch(`/card/${encodeURIComponent(cardId)}/ping`, { method: 'POST' }).catch(() => {});
    }

    ping();
    setInterval(ping, PING_INTERVAL_MS);
    window.addEventListener('focus', ping);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) ping();
    });

    document.querySelectorAll('[data-delete-card]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const ok = window.confirm('Delete this card and all its data now? This cannot be undone.');
            if (!ok) return;
            try {
                await fetch(`/card/${encodeURIComponent(cardId)}/delete`, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                });
            } catch (_) {
                /* deletion is best-effort from the client; expiry will catch it regardless */
            }
            window.location.href = '/';
        });
    });
})();
