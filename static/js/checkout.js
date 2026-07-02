(function () {
    const panel = document.getElementById('checkout-panel');
    if (!panel) return;

    const cardId = panel.dataset.cardId;
    const stripeConfigured = panel.dataset.stripeConfigured === 'true';
    const countryEl = document.getElementById('shipping-country');
    const methodEl = document.getElementById('shipping-method');
    const statusEl = document.getElementById('checkout-status');
    const checkoutBtn = document.getElementById('checkout-btn');
    const priceCard = document.getElementById('price-card');
    const priceShipping = document.getElementById('price-shipping');
    const priceTotal = document.getElementById('price-total');

    let currentQuote = null;

    function formatPence(pence) {
        return '£' + (pence / 100).toFixed(2);
    }

    function setStatus(msg, isError) {
        statusEl.textContent = msg || '';
        statusEl.classList.toggle('is-error', !!isError);
    }

    function populateMethods(methods) {
        methodEl.innerHTML = '';
        methods.forEach((m, i) => {
            const opt = document.createElement('option');
            opt.value = m.id;
            opt.textContent = m.label + ' — ' + formatPence(m.amount_pence);
            opt.dataset.amount = String(m.amount_pence);
            if (i === 0) opt.selected = true;
            methodEl.appendChild(opt);
        });
        methodEl.disabled = methods.length <= 1;
    }

    function updatePrices(quote) {
        const retail = quote.retail_pence;
        const selected = methodEl.selectedOptions[0];
        const shipping = selected ? parseInt(selected.dataset.amount, 10) : quote.shipping_pence;
        priceCard.textContent = formatPence(retail);
        priceShipping.textContent = formatPence(shipping);
        priceTotal.textContent = formatPence(retail + shipping);
        return shipping;
    }

    async function fetchQuote() {
        checkoutBtn.disabled = true;
        setStatus('Fetching shipping quote…');
        const country = countryEl.value;
        try {
            const res = await fetch('/api/card/' + encodeURIComponent(cardId) + '/quote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ country }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Quote failed');
            currentQuote = data;
            populateMethods(data.shipping_methods || []);
            updatePrices(data);
            if (stripeConfigured) {
                checkoutBtn.disabled = false;
                setStatus(data.message || 'Ready to checkout.');
            } else {
                setStatus('Stripe is not configured on this server yet.', true);
            }
        } catch (err) {
            setStatus(err.message || 'Could not fetch quote.', true);
        }
    }

    countryEl.addEventListener('change', fetchQuote);
    methodEl.addEventListener('change', () => {
        if (currentQuote) updatePrices(currentQuote);
    });

    checkoutBtn.addEventListener('click', async () => {
        if (!currentQuote) return;
        checkoutBtn.disabled = true;
        setStatus('Redirecting to secure checkout…');
        const shippingPence = updatePrices(currentQuote);
        const shippingMethod = methodEl.value;
        try {
            const res = await fetch('/api/card/' + encodeURIComponent(cardId) + '/checkout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    country: countryEl.value,
                    shipping_method: shippingMethod,
                    shipping_pence: shippingPence,
                }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Checkout failed');
            if (data.checkout_url) {
                window.location.href = data.checkout_url;
                return;
            }
            throw new Error('No checkout URL returned');
        } catch (err) {
            setStatus(err.message || 'Checkout failed.', true);
            checkoutBtn.disabled = false;
        }
    });

    fetchQuote();
})();
