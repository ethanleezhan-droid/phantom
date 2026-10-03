# 🌐 Phantom Wallet Simulator — Web Version

This is a browser-based version of the Phantom Wallet Simulator. The original
`wallet.py` is a **CustomTkinter desktop app** and is left completely
unchanged. This web version reuses the **exact same wallet logic, cryptography,
and data structures** and serves them over HTTP with a Flask backend and an
HTML/CSS/JS front-end that recreates the purple Phantom UI in the browser.

## What was added (nothing was removed or changed)

| File | Purpose |
|------|---------|
| `wallet_core.py` | The original backend from `wallet.py` — `SecurityManager` (AES/Fernet, RSA‑2048 signatures, HMAC‑SHA256, SHA‑256), the DSA classes (linked list, stack, queue, priority mempool, bubble sort), `COIN_METADATA`, and `WalletBackend` — with the desktop GUI removed so it runs headless. **No business logic changed.** |
| `app.py` | Flask server. Translates HTTP requests into calls on `WalletBackend`. Each browser session gets its own wallet instance. |
| `templates/index.html` | The single-page UI shell (splash → landing → terms → seed → dashboard, plus send/receive/history/profile modals). |
| `static/style.css` | Phantom purple theme (colors mirror the desktop app's constants). |
| `static/app.js` | Front-end logic; calls the API only — all crypto/DSA stays on the server. |
| `requirements-web.txt` | Python dependencies for the web version. |

`wallet.py` and all original assets/data are untouched, so the desktop app
still runs exactly as before.

## Run locally

```bash
pip install -r requirements-web.txt
python app.py
# open http://localhost:8000
```

Set a different port with `PORT=5000 python app.py`.

## Everything is preserved

- **Deterministic wallets** — the same 12-word seed always produces the same
  address and holdings (SHA‑256 of the seed phrase).
- **Security** — seed phrases are AES-encrypted for the logs, every
  transaction is signed (RSA‑2048) and authenticated (HMAC‑SHA256), IDs come
  from `secrets`.
- **DSA** — audit log is a linked list, undo is a stack, the processing
  pipeline is a queue, the mempool is a priority queue, and "Sort by Amount"
  in History runs the original bubble sort.
- **Persistence & logging** — wallets are still written to
  `admin/wallets.xlsx` (atomic writes) and `admin/audit_log.txt` /
  `admin/security_log.txt`.
- **Send / Receive / History / QR / Edit Profile** — all flows behave as in
  the desktop app (including the 2-second transaction confirmation).

## Deploying as a public website

`app.py` is a standard WSGI Flask app. For a persistent public site, run it
behind a production server, e.g.:

```bash
pip install gunicorn
gunicorn -w 1 -t 120 -b 0.0.0.0:8000 app:app
```

Use a single worker (`-w 1`) unless you add shared storage, because wallet
sessions are kept in memory per process. Set `FLASK_SECRET_KEY` to a stable
value so sessions survive restarts.

> ⚠️ This remains an **educational simulator**. No real blockchain, no real
> funds — exactly as described in the original project's Terms of Service.
