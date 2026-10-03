/* Phantom Simulator — front-end.
   This only drives screens and calls the Flask API. All wallet logic, crypto
   and DSA run server-side in wallet_core.py (the original wallet.py backend). */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const VIEWS = ["splash", "landing", "terms", "seed", "login", "dashboard"];
let COINS = {};            // coin metadata from /api/coins
let STATE = null;          // latest wallet state
let pollTimer = null;
let currentSeed = [];
let seedRevealed = false;
let histDescending = true;
let pfpFile = null;

/* ---------------- helpers ---------------- */
function showView(name) {
  VIEWS.forEach((v) => $("#view-" + v).classList.toggle("hidden", v !== name));
  if (name === "dashboard") startPolling();
  else stopPolling();
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.json();
}
async function postJSON(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 2000);
}

function fmtUSD(n) {
  return "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
// Mirror python's :.6g formatting for token amounts.
function fmt6g(n) {
  const s = Number(n).toPrecision(6);
  return parseFloat(s).toString();
}

async function copyText(text, done) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    ta.remove();
  }
  if (done) done();
}

/* ---------------- splash ---------------- */
function runSplash() {
  showView("splash");
  requestAnimationFrame(() => { $("#splash-bar").style.width = "100%"; });
  setTimeout(() => showView("landing"), 2500);
}

/* ---------------- terms ---------------- */
async function openTerms() {
  showView("terms");
  const box = $("#terms-body");
  const check = $("#terms-check");
  const cont = $("#terms-continue");
  const goend = $("#terms-goend");
  check.checked = false; check.disabled = true;
  cont.disabled = true;
  goend.classList.remove("done"); goend.textContent = "↓";
  let scrolledEnd = false;

  const { terms } = await api("/api/terms");
  box.innerHTML = "";
  (terms || "").split("\n\n").forEach((section) => {
    const lines = section.split("\n");
    if (!lines[0].trim()) return;
    const h = document.createElement("h4");
    h.textContent = lines[0];
    const p = document.createElement("p");
    p.textContent = lines.slice(1).join("\n");
    box.appendChild(h); box.appendChild(p);
  });

  const scroll = $("#terms-scroll");
  const markEnd = () => {
    if (scrolledEnd) return;
    scrolledEnd = true;
    check.disabled = false;
    goend.classList.add("done"); goend.textContent = "✓";
  };
  const onScroll = () => {
    if (scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 12) markEnd();
  };
  scroll.onscroll = onScroll;
  // If terms fit without scrolling, enable immediately.
  if (scroll.scrollHeight <= scroll.clientHeight + 12) markEnd();

  goend.onclick = () => { scroll.scrollTo({ top: scroll.scrollHeight, behavior: "smooth" }); markEnd(); };
  check.onchange = () => { cont.disabled = !(check.checked && scrolledEnd); };
}

/* ---------------- seed ---------------- */
function renderSeed() {
  const grid = $("#seed-grid");
  grid.innerHTML = "";
  currentSeed.forEach((word, i) => {
    const d = document.createElement("div");
    d.className = "seed-word";
    d.innerHTML = `<span class="n">${i + 1}</span><span class="w">${seedRevealed ? word : "****"}</span>`;
    grid.appendChild(d);
  });
}

/* ---------------- login inputs ---------------- */
function buildLoginInputs() {
  const wrap = $("#login-inputs");
  wrap.innerHTML = "";
  for (let i = 0; i < 12; i++) {
    const inp = document.createElement("input");
    inp.className = "seed-input";
    inp.placeholder = "Word " + (i + 1);
    inp.dataset.idx = i;
    inp.addEventListener("input", (e) => {
      const text = e.target.value.trim();
      if (text.includes(" ")) {
        const words = text.split(/\s+/);
        const inputs = $$("#login-inputs .seed-input");
        words.forEach((w, k) => { if (i + k < 12) inputs[i + k].value = w; });
      }
    });
    wrap.appendChild(inp);
  }
}

/* ---------------- dashboard ---------------- */
async function loadState() {
  STATE = await api("/api/state");
  renderDashboard();
  return STATE;
}

function renderDashboard() {
  if (!STATE || !STATE.logged_in) return;
  const w = STATE.wallet;
  $("#dash-address").textContent = w.address;
  $("#dash-name").textContent = w.name;
  $("#dash-balance").textContent = fmtUSD(w.balance);

  const av = $("#dash-avatar");
  if (w.pfp) av.innerHTML = `<img src="${w.pfp}?t=${Date.now()}" alt="pfp"/>`;
  else { av.textContent = "W"; }

  const h = $("#dash-holdings");
  h.innerHTML = "";
  STATE.holdings.forEach((c) => {
    const row = document.createElement("div");
    row.className = "holding";
    const icon = c.icon
      ? `<img class="holding__icon" src="${c.icon}" alt="" onerror="this.className='holding__icon fallback';this.replaceWith(Object.assign(document.createElement('div'),{className:'holding__icon fallback',textContent:'${c.token}'.slice(0,3)}))"/>`
      : `<div class="holding__icon fallback">${c.token.slice(0, 3)}</div>`;
    row.innerHTML = `
      ${icon}
      <div class="holding__info">
        <div class="holding__name">${c.name}</div>
        <div class="holding__price">${fmtUSD(c.price)}</div>
      </div>
      <div class="holding__right">
        <div class="holding__value">${fmtUSD(c.value)}</div>
        <div class="holding__amt">${fmt6g(c.amount)} ${c.token}</div>
      </div>`;
    h.appendChild(row);
  });
}

function startPolling() {
  stopPolling();
  // Reflect pending -> confirmed transitions and received funds (2s server delay).
  pollTimer = setInterval(async () => {
    STATE = await api("/api/state");
    if (!STATE.logged_in) { stopPolling(); return; }
    renderDashboard();
    if (!$("#modal-history").classList.contains("hidden")) renderHistory();
  }, 2500);
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

/* ---------------- modals ---------------- */
function openModal(id) {
  $("#modal-overlay").classList.remove("hidden");
  $$("#modal-overlay .modal").forEach((m) => m.classList.add("hidden"));
  $("#" + id).classList.remove("hidden");
}
function closeModal() {
  $("#modal-overlay").classList.add("hidden");
  $$("#modal-overlay .modal").forEach((m) => m.classList.add("hidden"));
}

/* ----- send ----- */
function openSend() {
  const sel = $("#send-token");
  sel.innerHTML = "";
  STATE.holdings.filter((c) => c.amount > 0).forEach((c) => {
    const o = document.createElement("option");
    o.value = c.token; o.textContent = c.token; sel.appendChild(o);
  });
  if (!sel.options.length) { const o = document.createElement("option"); o.value = "SOL"; o.textContent = "SOL"; sel.appendChild(o); }
  $("#send-addr").value = "";
  $("#send-amt").value = "";
  resetSendStep();
  $("#send-status").textContent = "";
  openModal("modal-send");
}
function resetSendStep() {
  $("#send-fee").classList.add("hidden");
  $("#send-step2").classList.add("hidden");
  $("#send-review").classList.remove("hidden");
}
function sendReview() {
  const addr = $("#send-addr").value.trim();
  const amtRaw = $("#send-amt").value.trim();
  const token = $("#send-token").value;
  const status = $("#send-status");
  const setErr = (m) => { status.className = "status err"; status.textContent = m; };

  if (!addr) return setErr("❌ Please enter recipient address");
  if (!amtRaw) return setErr("❌ Please enter amount");
  const amt = parseFloat(amtRaw);
  if (isNaN(amt)) return setErr("❌ Invalid amount format");
  if (amt <= 0) return setErr("❌ Amount must be greater than 0");

  const meta = COINS[token] || {};
  const fee = meta.fee || 0;
  const total = amt + fee;
  const holding = STATE.holdings.find((c) => c.token === token);
  const balance = holding ? holding.amount : 0;
  if (balance < total) {
    return setErr(`❌ Insufficient funds! You have ${fmt6g(balance)} ${token}, need ${fmt6g(total)} ${token}`);
  }

  const network = meta.network || "Unknown Network";
  const feeCoin = meta.fee_coin || token;
  const feeIcon = meta.fee_icon || meta.icon;
  const feeBox = $("#send-fee");
  feeBox.innerHTML = `
    <div class="net">🔗 ${network}</div>
    <div class="fee">${feeIcon ? `<img src="/assets/${feeIcon}" alt=""/>` : ""}Network Fee: ${fee} ${feeCoin}</div>`;
  feeBox.classList.remove("hidden");
  $("#send-review").classList.add("hidden");
  $("#send-step2").classList.remove("hidden");
  status.className = "status ok";
  status.textContent = "✓ Ready to send. Click 'Send Now' to confirm.";
}
async function sendNow() {
  const res = await postJSON("/api/send", {
    recipient: $("#send-addr").value.trim(),
    amount: $("#send-amt").value.trim(),
    token: $("#send-token").value,
  });
  const status = $("#send-status");
  if (res.ok) {
    status.className = "status ok"; status.textContent = res.message;
    STATE = res.state; renderDashboard();
    setTimeout(closeModal, 1400);
  } else {
    status.className = "status err"; status.textContent = res.message || res.error || "Error";
    resetSendStep();
  }
}

/* ----- receive ----- */
async function openReceive() {
  const sel = $("#receive-token");
  sel.innerHTML = "";
  (STATE.holdings.length ? STATE.holdings.map((c) => c.token) : ["SOL"]).forEach((t) => {
    const o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o);
  });
  $("#receive-address").textContent = STATE.wallet.address;
  $("#receive-amt").value = "";
  $("#receive-status").textContent = "";
  openModal("modal-receive");
  const qr = await api("/api/qr");
  if (qr && qr.data_uri) $("#receive-qr").src = qr.data_uri;
}
async function receiveNow() {
  const amt = $("#receive-amt").value.trim();
  if (!amt) return;
  const res = await postJSON("/api/receive", { token: $("#receive-token").value, amount: amt });
  const status = $("#receive-status");
  if (res.ok) {
    STATE = res.state; renderDashboard();
    closeModal();
    toast("✅ Incoming transfer simulated — confirming…");
  } else {
    status.className = "status err"; status.textContent = res.error || "Error";
  }
}

/* ----- history ----- */
function renderHistory() {
  const list = $("#hist-list");
  list.innerHTML = "";
  const hist = STATE && STATE.history ? STATE.history : [];
  if (!hist.length) {
    list.innerHTML = `<div class="empty">No transactions yet</div>`;
    return;
  }
  hist.forEach((tx) => {
    const isSend = tx.type === "send";
    const sign = isSend ? "-" : "+";
    const recipient = isSend ? `Sent to: ${(tx.recipient || "Unknown").slice(0, 20)}...` : "Received";
    const fee = isSend ? `Fee: ${fmt6g(tx.fee || 0)} ${tx.token}` : "";
    const el = document.createElement("div");
    el.className = "tx";
    el.innerHTML = `
      <div class="tx__top">
        <span class="tx__icon">${isSend ? "🔼" : "🔽"}</span>
        <div class="tx__main">
          <div class="tx__action">${tx.type.toUpperCase()} ${tx.token}</div>
          <div class="tx__status ${tx.status === "confirmed" ? "confirmed" : ""}">${(tx.status || "").toUpperCase()}</div>
        </div>
        <div class="tx__right">
          <div class="tx__amt ${isSend ? "send" : "receive"}">${sign}${fmt6g(tx.amount)}</div>
          ${fee ? `<div class="tx__fee">${fee}</div>` : ""}
        </div>
      </div>
      <div class="tx__meta">${recipient}<br/>${tx.time}</div>`;
    list.appendChild(el);
  });
}
async function openHistory() {
  renderHistory();
  openModal("modal-history");
}
async function sortByAmount() {
  histDescending = !histDescending;
  const res = await postJSON("/api/sort_history", { mode: "amount", descending: histDescending });
  if (res.ok) { STATE.history = res.history; renderHistory(); }
}
async function sortByTime() {
  const res = await postJSON("/api/sort_history", { mode: "time" });
  if (res.ok) { STATE.history = res.history; renderHistory(); }
}

/* ----- profile ----- */
function openProfile() {
  $("#profile-name").value = STATE.wallet.name || "";
  pfpFile = null;
  const prev = $("#profile-preview");
  if (STATE.wallet.pfp) prev.innerHTML = `<img src="${STATE.wallet.pfp}?t=${Date.now()}" alt="pfp"/>`;
  else prev.innerHTML = "No Image<br/>Selected";
  openModal("modal-profile");
}
async function saveProfile() {
  const fd = new FormData();
  fd.append("name", $("#profile-name").value);
  if (pfpFile) fd.append("pfp", pfpFile);
  const res = await api("/api/profile", { method: "POST", body: fd });
  if (res.ok) { STATE = res.state; renderDashboard(); closeModal(); toast("Profile updated"); }
}

/* ---------------- wiring ---------------- */
function wire() {
  // landing
  $("#btn-create").onclick = openTerms;
  $("#btn-have").onclick = () => { buildLoginInputs(); $("#login-error").textContent = ""; showView("login"); };

  // terms
  $("#terms-back").onclick = () => showView("landing");
  $("#terms-continue").onclick = async () => {
    const res = await postJSON("/api/create", {});
    if (res.ok) {
      currentSeed = res.seed || [];
      seedRevealed = false;
      $("#seed-reveal").textContent = "👁 Reveal";
      renderSeed();
      showView("seed");
    }
  };

  // seed
  $("#seed-reveal").onclick = () => {
    seedRevealed = !seedRevealed;
    $("#seed-reveal").textContent = seedRevealed ? "👁 Hide" : "👁 Reveal";
    renderSeed();
  };
  $("#seed-copy").onclick = () => copyText(currentSeed.join(" "), () => {
    const b = $("#seed-copy"); b.textContent = "✓ Copied!";
    setTimeout(() => (b.textContent = "📋 Copy"), 2000);
  });
  $("#seed-finish").onclick = async () => { await loadState(); showView("dashboard"); };

  // login
  $("#login-back").onclick = () => showView("landing");
  $("#login-import").onclick = async () => {
    const words = $$("#login-inputs .seed-input").map((i) => i.value.trim().toLowerCase());
    const res = await postJSON("/api/import", { words });
    if (res.ok) { STATE = res.state; renderDashboard(); showView("dashboard"); }
    else $("#login-error").textContent = res.error || "❌ Invalid seed phrase. Try again.";
  };

  // dashboard
  $("#dash-copy").onclick = () => copyText(STATE.wallet.address, () => {
    const b = $("#dash-copy"); b.textContent = "✓";
    setTimeout(() => (b.textContent = "📋"), 1500);
  });
  $("#dash-logout").onclick = async () => { await postJSON("/api/logout", {}); showView("landing"); };
  $("#dash-edit").onclick = openProfile;
  $("#act-send").onclick = openSend;
  $("#act-receive").onclick = openReceive;
  $("#act-history").onclick = openHistory;

  // modals
  $$(".modal-close").forEach((b) => (b.onclick = closeModal));
  $("#modal-overlay").addEventListener("click", (e) => { if (e.target.id === "modal-overlay") closeModal(); });

  $("#send-review").onclick = sendReview;
  $("#send-cancel").onclick = () => { resetSendStep(); $("#send-status").textContent = ""; };
  $("#send-now").onclick = sendNow;

  $("#receive-copy").onclick = () => copyText(STATE.wallet.address, () => {
    const b = $("#receive-copy"); b.textContent = "✓";
    setTimeout(() => (b.textContent = "📋"), 1500);
  });
  $("#receive-now").onclick = receiveNow;

  $("#hist-sort-amt").onclick = sortByAmount;
  $("#hist-sort-time").onclick = sortByTime;

  $("#profile-upload").onclick = () => $("#profile-file").click();
  $("#profile-file").onchange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    pfpFile = f;
    const reader = new FileReader();
    reader.onload = (ev) => { $("#profile-preview").innerHTML = `<img src="${ev.target.result}" alt="pfp"/>`; };
    reader.readAsDataURL(f);
  };
  $("#profile-save").onclick = saveProfile;
}

/* ---------------- boot ---------------- */
(async function init() {
  wire();
  COINS = await api("/api/coins");
  runSplash();
})();
