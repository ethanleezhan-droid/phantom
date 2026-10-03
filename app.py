"""
app.py
======

Flask web server for the Phantom Wallet Simulator.

This turns the (unchanged) desktop wallet logic in ``wallet_core.py`` into a
real website. Every piece of wallet behaviour — deterministic seed phrases,
AES/RSA/HMAC/SHA-256 security, the DSA structures (linked list, stack, queue,
priority mempool, bubble sort), simulated send/receive, Excel persistence and
audit/security logging — is executed by ``WalletBackend`` exactly as in the
original ``wallet.py``. This layer only translates HTTP requests into calls on
that backend and renders the Phantom UI in the browser.

Each browser session gets its own ``WalletBackend`` instance so multiple
visitors do not share a wallet.

Run:
    python app.py
Then open http://localhost:8000
"""

import io
import os
import base64
import threading
import tempfile

from flask import (
    Flask, render_template, request, jsonify, session,
    send_from_directory, abort,
)

import qrcode

from wallet_core import WalletBackend, COIN_METADATA, load_text_file, ASSETS_PATH

# Make all relative paths used by the backend (admin/, assets/, data/) resolve
# against the project root, regardless of where the server is launched from.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)

app = Flask(__name__)
# Ephemeral per-process secret — fine for a demo/simulator. Override with the
# FLASK_SECRET_KEY environment variable for a stable deployment.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())

# ----------------------------------------------------------------------------
# Per-session wallet backends
# ----------------------------------------------------------------------------
_SESSIONS = {}
_SESSIONS_LOCK = threading.Lock()


def get_backend():
    """Return the WalletBackend for the current browser session, creating one
    on first use. Each session is isolated so visitors don't share a wallet."""
    sid = session.get("sid")
    if not sid:
        sid = os.urandom(16).hex()
        session["sid"] = sid
    with _SESSIONS_LOCK:
        backend = _SESSIONS.get(sid)
        if backend is None:
            backend = WalletBackend()
            _SESSIONS[sid] = backend
    return backend


# ----------------------------------------------------------------------------
# Serialization helpers (backend objects -> JSON-friendly dicts)
# ----------------------------------------------------------------------------
def coin_icon_url(token):
    # Mirror DashboardView: tokens without their own metadata icon (e.g. MATIC,
    # whose metadata key is "POL") fall back to the bitcoin icon.
    icon = COIN_METADATA.get(token, {}).get("icon", "bitcoin_btc_icon_transparent.png")
    return f"/assets/{icon}"


def serialize_pfp(backend):
    """Return a browser-usable URL for the wallet profile picture, if any."""
    if not backend.wallet_data:
        return None
    pfp = backend.wallet_data.get("pfp")
    if pfp and os.path.exists(pfp):
        # pfp is stored as e.g. "assets/<id>_name.png"
        return "/" + pfp.replace(os.sep, "/")
    return None


def serialize_holdings(backend):
    # Mirror DashboardView: sort by value desc, hide zero/negative amounts.
    sorted_holdings = sorted(
        backend.holdings.items(),
        key=lambda x: x[1]["amount"] * x[1]["price"],
        reverse=True,
    )
    out = []
    for token, data in sorted_holdings:
        if data["amount"] <= 0:
            continue
        meta = COIN_METADATA.get(token, {})
        out.append({
            "token": token,
            "name": meta.get("name", token),
            "icon": coin_icon_url(token),
            "price": data["price"],
            "amount": data["amount"],
            "value": data["amount"] * data["price"],
        })
    return out


def serialize_history(backend):
    out = []
    for tx in backend.history:
        t = tx.get("time")
        if hasattr(t, "strftime"):
            time_str = t.strftime("%b %d, %H:%M")
        else:
            time_str = str(t)
        out.append({
            "id": tx.get("id"),
            "type": tx.get("type"),
            "token": tx.get("token"),
            "amount": tx.get("amount"),
            "fee": tx.get("fee", 0),
            "recipient": tx.get("recipient"),
            "status": tx.get("status"),
            "hash": tx.get("hash"),
            "time": time_str,
        })
    return out


def serialize_state(backend):
    if backend.wallet_data is None:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "wallet": {
            "name": backend.wallet_data.get("name"),
            "address": backend.wallet_data.get("address"),
            "balance": backend.wallet_data.get("balance", 0.0),
            "pfp": serialize_pfp(backend),
        },
        "holdings": serialize_holdings(backend),
        "history": serialize_history(backend),
    }


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(os.path.join(PROJECT_ROOT, ASSETS_PATH), filename)


# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------
@app.route("/api/coins")
def api_coins():
    """Coin metadata so the Send screen can preview network + fee, exactly like
    the desktop SendWindow."""
    return jsonify(COIN_METADATA)


@app.route("/api/terms")
def api_terms():
    return jsonify({"terms": load_text_file("TERMS_OF_SERVICE.txt")})


@app.route("/api/state")
def api_state():
    backend = get_backend()
    return jsonify(serialize_state(backend))


@app.route("/api/create", methods=["POST"])
def api_create():
    """Create a brand new wallet with a random 12-word seed (LandingView ->
    Terms -> SeedView path, which calls backend.create_wallet())."""
    backend = get_backend()
    backend.create_wallet()
    seed = backend.wallet_data["seed"] if backend.wallet_data else []
    return jsonify({"ok": True, "seed": seed, "state": serialize_state(backend)})


@app.route("/api/import", methods=["POST"])
def api_import():
    """Import an existing wallet from a 12-word seed phrase (LoginView)."""
    backend = get_backend()
    data = request.get_json(silent=True) or {}
    words = data.get("words")
    if isinstance(words, list):
        phrase = " ".join(str(w).strip().lower() for w in words if str(w).strip())
    else:
        phrase = str(data.get("phrase", "")).strip().lower()

    # Mirror LoginView.do_login validation (exactly 12 non-empty words).
    non_empty = [w for w in phrase.split() if w]
    if len(non_empty) != 12:
        return jsonify({"ok": False, "error": "❌ Please enter exactly 12 words"})

    if backend.login(" ".join(non_empty)):
        return jsonify({"ok": True, "state": serialize_state(backend)})
    return jsonify({"ok": False, "error": "❌ Invalid seed phrase. Try again."})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    backend = get_backend()
    backend.logout()
    return jsonify({"ok": True})


@app.route("/api/send", methods=["POST"])
def api_send():
    backend = get_backend()
    data = request.get_json(silent=True) or {}
    recipient = data.get("recipient", "")
    amount = data.get("amount", "")
    token = data.get("token", "")
    # backend returns a user-facing message string ("✅ ..." or "❌ ...").
    result = backend.send_transaction_execute(recipient, amount, token)
    success = isinstance(result, str) and result.startswith("✅")
    return jsonify({"ok": success, "message": result, "state": serialize_state(backend)})


@app.route("/api/receive", methods=["POST"])
def api_receive():
    backend = get_backend()
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    try:
        amount = float(data.get("amount", ""))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid amount"})
    if amount <= 0:
        return jsonify({"ok": False, "error": "Amount must be greater than 0"})
    backend.receive_transaction(amount, token)
    return jsonify({"ok": True, "state": serialize_state(backend)})


@app.route("/api/sort_history", methods=["POST"])
def api_sort_history():
    backend = get_backend()
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "time")
    if mode == "amount":
        descending = bool(data.get("descending", True))
        backend.sort_history_by_amount(descending)  # DSA: bubble sort
    # "time" mode: history is already newest-first; just return current order.
    return jsonify({"ok": True, "history": serialize_history(backend)})


@app.route("/api/profile", methods=["POST"])
def api_profile():
    """Update wallet name and optional profile picture (EditProfileWindow)."""
    backend = get_backend()
    if backend.wallet_data is None:
        return jsonify({"ok": False, "error": "No wallet"})

    new_name = request.form.get("name", "")
    pfp_path = None
    file = request.files.get("pfp")
    if file and file.filename:
        # Save the upload to a temp file, then let the backend copy it into
        # assets/ exactly as the desktop app does.
        suffix = os.path.splitext(file.filename)[1] or ".png"
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        file.save(tmp)
        pfp_path = tmp

    backend.update_wallet_metadata(new_name, pfp_path)

    if pfp_path:
        try:
            os.remove(pfp_path)
        except OSError:
            pass

    return jsonify({"ok": True, "state": serialize_state(backend)})


@app.route("/api/qr")
def api_qr():
    """QR code for the current wallet address, matching ReceiveWindow
    ('phantom:<address>')."""
    backend = get_backend()
    if backend.wallet_data is None:
        abort(404)
    qr_data = f"phantom:{backend.wallet_data['address']}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return jsonify({"data_uri": f"data:image/png;base64,{encoded}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
