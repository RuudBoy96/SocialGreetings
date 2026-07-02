# Testing SocialGreetings — full order flow

This guide walks you through testing the site locally, paying with Stripe test mode, and (optionally) sending a real printed card to your own address.

---

## 1. Local preview (no accounts)

### Start the server

**Windows:** double-click `start.bat`, or:

```powershell
cd "path\to\Test 1"
.\.venv\Scripts\python.exe app.py
```

Open **http://localhost:5000**

### What to check

| Step | URL / action | Expected |
|------|----------------|----------|
| Landing hero | `/` | Jamie and Laura cards alternate every ~12s with profile photos, dense chat bubbles, WhatsApp wallpaper |
| Create card | `/create` → upload a `.txt` chat export | Redirects to `/card/<id>` |
| Wallpaper on preview | Card preview page | Chat area shows doodle wallpaper (not flat cream) |
| Watermark | Card preview | “SocialGreetings · Preview” overlay; no free PDF download on toolbar |
| Order page | **Order printed card** | Shipping quote, price breakdown |
| Sample PDF | **Download watermarked sample PDF** on order page | PDF with watermark baked in |

**Sample file in repo:** `WhatsApp Chat with Kim Butler.txt`

---

## 2. Environment variables

Copy `.env.example` to `.env` in the project root:

```env
SECRET_KEY=your-random-secret
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
PRODIGI_API_KEY=your-prodigi-key
PRODIGI_SANDBOX=true
PRODIGI_GREETING_CARD_SKU=GLOBAL-CARD-5X7
CARD_PRICE_PENCE=1299
PUBLIC_BASE_URL=https://your-public-url
```

Restart the server after changing `.env`.

---

## 3. Stripe test checkout (no real charge)

1. Create a [Stripe](https://stripe.com) account → stay in **Test mode**
2. **Developers → API keys** → copy `sk_test_...` into `STRIPE_SECRET_KEY`
3. Restart the app → **Order & pay** should be enabled on the order page
4. Click **Order & pay** → Stripe Checkout opens
5. Pay with test card: **`4242 4242 4242 4242`**, any future expiry, any CVC
6. Enter your **real delivery address** — safe in test mode (no charge)

After payment you should land on `/order/<id>/success` with a clean PDF download link.

---

## 4. Webhooks (required for auto-fulfilment)

Stripe cannot call `localhost` directly. Use one of:

### Option A — Stripe CLI (recommended)

```powershell
stripe login
stripe listen --forward-to localhost:5000/webhooks/stripe
```

Copy the `whsec_...` signing secret into `STRIPE_WEBHOOK_SECRET`.

### Option B — ngrok

```powershell
ngrok http 5000
```

Register `https://xxxx.ngrok-free.app/webhooks/stripe` in Stripe Dashboard → Webhooks → `checkout.session.completed`.

The success page also verifies the session if the webhook is delayed.

---

## 5. Prodigi print fulfilment

| Mode | `PRODIGI_SANDBOX` | Result |
|------|-------------------|--------|
| Sandbox | `true` | API calls work; orders are **simulated** — no real print or shipment |
| Live | `false` + live API key | **Real** print and delivery |

### Sandbox testing

1. Sign up at [prodigi.com/print-api](https://www.prodigi.com/print-api/)
2. Copy sandbox API key → `PRODIGI_API_KEY`
3. Set `PRODIGI_SANDBOX=true`
4. After Stripe test payment, check success page for `prodigi_order_id` (or `fulfillment_status` in card data)

### Real card to your address

1. Prodigi **live** API key
2. Correct `PRODIGI_GREETING_CARD_SKU` from Prodigi product catalog (5×7 portrait)
3. `PUBLIC_BASE_URL` must be a **public HTTPS URL** Prodigi can reach to download print assets
4. Stripe **live** keys if you want a real charge (or use test mode only to validate payment UI)

For local dev, set `PUBLIC_BASE_URL` to your ngrok URL, e.g. `https://abc123.ngrok-free.app`.

---

## 6. Do you need a domain?

| Scenario | Domain needed? |
|----------|----------------|
| Local dev + Stripe CLI | No |
| Local dev + Prodigi asset fetch | No — use **ngrok** as `PUBLIC_BASE_URL` |
| Production with stable URL | Yes (or use host URL like `yourapp.railway.app`) |

### Where to buy (UK-friendly)

- [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) — at-cost pricing
- [Namecheap](https://www.namecheap.com/) — popular, cheap `.com` / `.co.uk`
- [Porkbun](https://porkbun.com/) — low renewal prices

You **do not** need a domain to test checkout and fulfilment locally with ngrok.

### Typical production setup

1. Deploy app (Railway, Render, Fly.io, VPS)
2. Point domain DNS → hosting provider (or use platform subdomain)
3. `PUBLIC_BASE_URL=https://yourdomain.com`
4. Stripe live webhook → `https://yourdomain.com/webhooks/stripe`
5. Prodigi live key + SKU

---

## 7. End-to-end checklist

- [ ] Landing hero cycles Jamie → Laura with photos and dense messages
- [ ] Generated card shows WhatsApp wallpaper on chat pages
- [ ] Watermarked preview; sample PDF has watermark
- [ ] Order page quote and total display correctly
- [ ] Stripe test payment completes
- [ ] Success page shows paid status + clean PDF download
- [ ] Webhook fires (`checkout.session.completed`)
- [ ] Prodigi order ID saved (sandbox or live)
- [ ] Paid card retained for 7 days

---

## 8. Troubleshooting

| Problem | Fix |
|---------|-----|
| **Order & pay** disabled | Set `STRIPE_SECRET_KEY` and restart |
| Payment succeeds but card not marked paid | Configure webhook (`STRIPE_WEBHOOK_SECRET` + Stripe CLI or ngrok) |
| Prodigi fulfilment failed | Check logs; ensure `PUBLIC_BASE_URL` is publicly reachable |
| PDF generation fails | Run `playwright install chromium` |
| Flat cream background on card | Fixed in app — recreate card; old cards with `platform: auto` still get wallpaper via CSS fallback |
| Card expired | Unpaid cards delete after 30 minutes — create a new one |

---

## 9. Quick test commands

```powershell
# Create a card via curl (PowerShell)
curl.exe -F "chat_file=@WhatsApp Chat with Kim Butler.txt" `
  -F "orientation=portrait" `
  http://localhost:5000/create

# Fetch shipping quote
curl.exe -X POST http://localhost:5000/api/card/CARD_ID/quote `
  -H "Content-Type: application/json" `
  -d "{\"country\":\"GB\"}"
```

Replace `CARD_ID` with the ID from the create redirect.
